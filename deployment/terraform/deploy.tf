resource "null_resource" "app_deployment" {
  triggers = {
    # Trigger on any change to the deployment script or backend templates
    # Trigger on any change to the deployment script
    script_sha = sha256(file("../../deployment/deploy_sw.py"))
  }

  depends_on = [
    google_secret_manager_secret_version.system_authz_version,
    google_secret_manager_secret_version.finance_policy_version,
    google_secret_manager_secret_version.opa_config_version
  ]

  provisioner "local-exec" {
    working_dir = "${path.module}/../../"
    command = <<EOT
      python3 -m venv .deploy_venv && \
      export PATH=$PATH:/opt/homebrew/bin && \
      source .deploy_venv/bin/activate && \
      pip install --upgrade --quiet --extra-index-url https://pypi.org/simple keyrings.google-artifactregistry-auth && \
      pip install --upgrade --quiet --extra-index-url https://pypi.org/simple google-cloud-aiplatform google-adk PyYAML langchain langchain-google-vertexai && \
      python3 deployment/deploy_sw.py \
        --project-id ${var.project_id} \
        --region ${var.region}
    EOT
  }
}
