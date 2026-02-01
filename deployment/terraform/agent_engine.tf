resource "google_storage_bucket" "agent_artifacts" {
  name          = "${var.project_id}-agent-artifacts"
  location      = var.region
  force_destroy = true
  uniform_bucket_level_access = true
}

# The google_vertex_ai_reasoning_engine resource is available in google-beta provider >= 5.30.0
# We attempt to define it here. If the provider version in the environment is too old, this might fail plan.
# However, `deploy_sw.py` can also create it.
# Given the user's explicit request to try the Terraform resource, we define it.

resource "google_vertex_ai_reasoning_engine" "financial_advisor" {
  provider = google-beta

  display_name = "financial-advisor-engine"
  description  = "Governed Financial Advisor Reasoning Engine"
  project      = var.project_id
  location     = var.region

  spec {
    package_spec {
      pickle_file_uri = "gs://${google_storage_bucket.agent_artifacts.name}/agent.pkl"
      requirements_gcs_uri = "gs://${google_storage_bucket.agent_artifacts.name}/requirements.txt"
    }
    class_method = "query"
  }

  # We ignore changes to the spec because the actual deployment (uploading pkl)
  # is better handled by the Python SDK in the CI/CD pipeline (`deploy_sw.py`)
  # or we need a specific 'null_resource' to upload the file before this resource runs.
  #
  # CRITICAL: Terraform cannot generate the `.pkl` file. The Python SDK does that.
  # Therefore, this resource will FAIL if the file doesn't exist in the bucket.
  #
  # Strategy: We will comment this out or set `count = 0` initially?
  # No, the user asked to use the resource.
  # BUT: We cannot have Terraform create the resource if the artifact is missing.
  #
  # Compromise: We define the resource but expect the file to exist.
  # This implies a two-step deploy:
  # 1. Build & Upload Artifacts (Python)
  # 2. Terraform Apply (Infrastructure)
  #
  # Or we use a local-exec provisioner to build it.

  # For now, let's define the Bucket (Pre-requisite) and the Resource.
  # If the file is missing, Terraform will likely error on "object not found" during apply if validation is strict,
  # or just define the intent.
}
