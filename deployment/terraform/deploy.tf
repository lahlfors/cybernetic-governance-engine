# Serverless Deployment Trigger
# This deploys the application using deploy_sw.py after infrastructure is ready.
# Uses Agent Engine (Vertex AI) + Cloud Run architecture (no GKE/Redis needed).

resource "null_resource" "app_deployment" {
  triggers = {
    # Trigger on any change to the deployment script
    script_sha = sha256(file("../../deployment/deploy_sw.py"))
    # Trigger on gateway image change
    gateway_image = var.gateway_image
  }

  depends_on = [
    google_cloud_run_v2_service.gateway,
    google_secret_manager_secret_version.system_authz_version,
    google_secret_manager_secret_version.finance_policy_version,
    google_secret_manager_secret_version.opa_config_version,
    google_storage_bucket.agent_artifacts,
    google_artifact_registry_repository.repo
  ]

  provisioner "local-exec" {
    working_dir = "${path.module}/../../"
    command = <<EOT
      python3 -m venv .deploy_venv && \
      export PATH=$PATH:/opt/homebrew/bin && \
      source .deploy_venv/bin/activate && \
      pip install --upgrade --quiet --extra-index-url https://pypi.org/simple keyrings.google-artifactregistry-auth && \
      pip install --upgrade --quiet --extra-index-url https://pypi.org/simple . && \
      python3 deployment/deploy_sw.py \
        --project-id ${var.project_id} \
        --region ${var.region}
    EOT
  }
}
