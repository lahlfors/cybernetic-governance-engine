from kfp.dsl import component, Output, Artifact

@component(base_image="python:3.9", packages_to_install=["google-cloud-run", "google-cloud-aiplatform"])
def run_transpiler_job_op(
    project_id: str,
    location: str,
    bucket_name: str,
    stamp_config_blob: str,
    output_policy: Output[Artifact]
):
    """
    Triggers a Cloud Run Job to transpile STAMP to OPA Rego.
    This component acts as the bridge between the Vertex AI Pipeline and the serverless
    Transpiler Job (which contains the Transpiler + Judge Agent logic).
    """
    import logging
    from google.cloud import run_v2

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("kfp.components.transpiler")

    job_name = f"projects/{project_id}/locations/{location}/jobs/governance-transpiler-job"

    logger.info(f"Triggering Cloud Run Job: {job_name}")
    logger.info(f"Input STAMP Blob: gs://{bucket_name}/{stamp_config_blob}")

    # Initialize Cloud Run Client
    client = run_v2.JobsClient()

    # Construct execution request with overrides
    # Pass the STAMP location and Output URI as env vars
    request = run_v2.RunJobRequest(
        name=job_name,
        overrides=run_v2.RunJobRequest.Overrides(
            container_overrides=[
                run_v2.RunJobRequest.Overrides.ContainerOverride(
                    env=[
                        run_v2.EnvVar(name="POLICY_REGISTRY_BUCKET", value=bucket_name),
                        run_v2.EnvVar(name="STAMP_CONFIG_BLOB", value=stamp_config_blob),
                        run_v2.EnvVar(name="OUTPUT_ARTIFACT_URI", value=output_policy.uri)
                    ]
                )
            ]
        )
    )

    try:
        operation = client.run_job(request=request)
        logger.info(f"Job triggered. Operation: {operation.operation.name}")

        # Wait for completion (Cloud Run Jobs are async, but KFP component waits)
        response = operation.result() # Blocks until job completes

        logger.info(f"Job completed successfully: {response}")

        # Write metadata to the output artifact to signal success
        with open(output_policy.path, "w") as f:
            f.write(f"Policy generated successfully from gs://{bucket_name}/{stamp_config_blob}")

    except Exception as e:
        logger.error(f"Failed to execute Transpiler Job: {e}")
        raise e
