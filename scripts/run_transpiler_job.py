import os
import sys
import logging
import json
import tarfile
import io
import time
from src.governance.policy_loader import PolicyLoader
from src.governance.transpiler import transpiler
from src.agents.risk_analyst.agent import ProposedUCA, ConstraintLogic
from google.cloud import storage

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TranspilerJob")

def create_opa_bundle(rego_code: str) -> io.BytesIO:
    """
    Packages the generated Rego code into a valid OPA bundle tarball (in-memory).
    """
    bundle_buffer = io.BytesIO()
    with tarfile.open(fileobj=bundle_buffer, mode="w:gz") as tar:
        # Create a TarInfo object for the policy file
        policy_info = tarfile.TarInfo(name="policy.rego")
        policy_data = rego_code.encode("utf-8")
        policy_info.size = len(policy_data)

        # Add the file to the tarball
        tar.addfile(policy_info, io.BytesIO(policy_data))

        # OPA requires a manifest (optional but good practice)
        # We'll skip complex manifest for now and just rely on the rego file structure

    bundle_buffer.seek(0)
    return bundle_buffer

def upload_to_gcs(bucket_name: str, blob_name: str, data: io.BytesIO, content_type: str):
    """
    Uploads data to GCS using ADC.
    """
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_file(data, content_type=content_type)
        logger.info(f"Successfully uploaded to gs://{bucket_name}/{blob_name}")
    except Exception as e:
        logger.error(f"Failed to upload to GCS: {e}")
        raise e

def main():
    """
    Entrypoint for the Cloud Run Transpiler Job.
    1. Loads STAMP spec from GCS (via PolicyLoader).
    2. Transpiles hazards to OPA/NeMo code.
    3. Uploads the OPA Bundle (.tar.gz) and Evidence Artifact (.json) to GCS.
    """
    bucket_name = os.getenv("POLICY_REGISTRY_BUCKET")
    blob_name = os.getenv("STAMP_CONFIG_BLOB", "current_stamp_spec.yaml")

    if not bucket_name:
        logger.error("POLICY_REGISTRY_BUCKET env var not set.")
        sys.exit(1)

    logger.info(f"Starting Transpiler Job. Source: gs://{bucket_name}/{blob_name}")

    # 1. Load STAMP Specification
    loader = PolicyLoader(bucket_name=bucket_name)
    hazards = loader.load_stamp_hazards(blob_name=blob_name)

    if not hazards:
        logger.error("No hazards found or failed to load spec.")
        sys.exit(1)

    # 2. Convert raw dicts to ProposedUCA objects
    ucas = []
    for h in hazards:
        try:
            logic_data = h.get("logic", {})
            logic = ConstraintLogic(
                variable=logic_data.get("variable"),
                operator=logic_data.get("operator"),
                threshold=logic_data.get("threshold"),
                condition=logic_data.get("condition")
            )
            uca = ProposedUCA(
                category="General",
                hazard=h.get("hazard"),
                description=h.get("description"),
                constraint_logic=logic
            )
            ucas.append(uca)
        except Exception as e:
            logger.warning(f"Skipping malformed hazard: {h}. Error: {e}")

    logger.info(f"Parsed {len(ucas)} valid UCAs.")

    # 3. Transpile & Verify (includes Judge Agent)
    python_code, rego_code = transpiler.transpile_policy(ucas)

    logger.info("Transpilation Complete.")

    # 4. Production Uploads

    # A. Upload Evidence Artifact (JSON)
    evidence = {
        "timestamp": time.time(),
        "source_stamp": blob_name,
        "stamp_input": [h.dict() if hasattr(h, 'dict') else h for h in hazards],
        "generated_rego": rego_code,
        "generated_python": python_code,
        "verification_status": "JUDGED_AND_APPROVED"
    }

    evidence_blob_name = f"evidence/evidence_{int(time.time())}.json"
    evidence_buffer = io.BytesIO(json.dumps(evidence, indent=2).encode("utf-8"))
    upload_to_gcs(bucket_name, evidence_blob_name, evidence_buffer, "application/json")

    # B. Upload OPA Bundle (Tarball)
    # Target path matches opa_config.yaml: 'bundles/finance/latest.tar.gz'
    bundle_blob_name = "bundles/finance/latest.tar.gz"
    bundle_buffer = create_opa_bundle(rego_code)
    upload_to_gcs(bucket_name, bundle_blob_name, bundle_buffer, "application/x-tar")

    print(f"Job Complete. OPA Bundle updated at gs://{bucket_name}/{bundle_blob_name}")

if __name__ == "__main__":
    main()
