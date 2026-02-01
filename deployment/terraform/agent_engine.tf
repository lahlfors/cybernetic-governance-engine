resource "google_storage_bucket" "agent_artifacts" {
  name          = "${var.project_id}-agent-artifacts"
  location      = var.region
  force_destroy = true
  uniform_bucket_level_access = true
}

# The google_vertex_ai_reasoning_engine resource is intentionally commented out.
# We are using the Python SDK (`deploy_sw.py`) to create and manage this resource
# because it requires imperative steps (pickling Python code) that are better handled in the CD pipeline code.

# resource "google_vertex_ai_reasoning_engine" "financial_advisor" {
#   provider = google-beta
#
#   display_name = "financial-advisor-engine"
#   description  = "Governed Financial Advisor Reasoning Engine"
#   project      = var.project_id
#   location     = var.region
#
#   spec {
#     package_spec {
#       pickle_file_uri = "gs://${google_storage_bucket.agent_artifacts.name}/agent.pkl"
#       requirements_gcs_uri = "gs://${google_storage_bucket.agent_artifacts.name}/requirements.txt"
#     }
#     class_method = "query"
#   }
# }
