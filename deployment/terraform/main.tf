
# Artifact Registry for Container Images
resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = "governance-stack"
  description   = "Docker repository for Governed Financial Advisor"
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}
