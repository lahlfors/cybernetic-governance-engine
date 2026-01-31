resource "google_project_service" "apis" {
  for_each = toset([
    "aiplatform.googleapis.com",
    "cloudbuild.googleapis.com",
    "container.googleapis.com",
    "firestore.googleapis.com",
    "logging.googleapis.com",
    "redis.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
  ])

  project = var.project_id
  service = each.key

  disable_on_destroy = false
}
