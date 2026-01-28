import json
import logging
import os
import yaml
from typing import List, Dict, Optional
from google.cloud import storage

logger = logging.getLogger("Governance.PolicyLoader")

class PolicyLoader:
    """
    Production Policy Registry Client.
    Fetches STAMP specifications and Policy Bundles directly from Google Cloud Storage (GCS)
    using Application Default Credentials (ADC) managed by the Cloud Run identity.
    """

    def __init__(self, bucket_name: Optional[str] = None):
        """
        Args:
            bucket_name: The GCS bucket name. If None, attempts to read from env var 'POLICY_REGISTRY_BUCKET'.
        """
        self.bucket_name = bucket_name or os.getenv("POLICY_REGISTRY_BUCKET")
        self.client = None

        # Initialize GCS Client (Lazy Load)
        if self.bucket_name:
            try:
                self.client = storage.Client()
            except Exception as e:
                logger.warning(f"Could not initialize GCS Client (likely no ADC found): {e}")

    def load_stamp_hazards(self, blob_name: str = "current_stamp_spec.yaml") -> List[Dict]:
        """
        Fetches and parses the STAMP specification from GCS.
        Supports both JSON and YAML formats.
        """
        if not self.client or not self.bucket_name:
            logger.error("GCS Client or Bucket Name not configured. Cannot load policy.")
            return []

        try:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(blob_name)

            content_str = blob.download_as_text()

            if blob_name.endswith(".yaml") or blob_name.endswith(".yml"):
                data = yaml.safe_load(content_str)
            else:
                data = json.loads(content_str)

            # Normalize: Expecting a list of hazards, or a dict with "hazards" key
            hazards = data if isinstance(data, list) else data.get("hazards", [])

            logger.info(f"Successfully loaded {len(hazards)} hazards from gs://{self.bucket_name}/{blob_name}")
            return hazards

        except Exception as e:
            logger.error(f"Failed to load STAMP spec from GCS: {e}")
            return []

    def format_as_prompt_context(self, blob_name: str = "current_stamp_spec.yaml") -> str:
        """
        Formats the loaded hazards into a string suitable for LLM context injection.
        """
        hazards = self.load_stamp_hazards(blob_name)
        if not hazards:
            return "No specific hazards defined in registry."

        formatted = []
        for i, h in enumerate(hazards, 1):
            logic = h.get("logic", {})

            # Handle Deontic Modals (Obligations/Prohibitions) if present
            deontic = h.get("deontic_modal", "PROHIBITION") # Default to Prohibition (Safety Constraint)

            block = f"""
{i}. {h.get('hazard', 'Unknown Hazard')} ({deontic}):
   - Description: "{h.get('description', '')}"
   - Logic: variable="{logic.get('variable')}", operator="{logic.get('operator')}", threshold="{logic.get('threshold')}", condition="{logic.get('condition')}"
"""
            formatted.append(block)

        return "".join(formatted)
