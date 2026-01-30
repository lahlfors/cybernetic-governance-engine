resource "google_storage_bucket" "agent_artifacts" {
  name                        = "${var.project_id}-agent-artifacts"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true
}
