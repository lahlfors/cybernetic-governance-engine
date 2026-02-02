resource "google_cloud_run_v2_service" "nemo_service" {
  name     = "nemo-guardrails-service"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL" # Or INTERNAL_AND_CLOUD_LOAD_BALANCING if we only want Gateway/Agent to call it

  template {
    containers {
      image = "gcr.io/${var.project_id}/nemo-guardrails-service:latest"
      ports {
        container_port = 8080
      }
      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "REGION"
        value = var.region
      }
      env {
        name = "RAILS_CONFIG_PATH"
        value = "/app/config/rails"
      }
      # Resources for NeMo (it can be heavy)
      resources {
        limits = {
          cpu    = "2000m"
          memory = "2Gi"
        }
      }
    }
  }
}

output "nemo_service_url" {
  value = google_cloud_run_v2_service.nemo_service.uri
}

resource "google_secret_manager_secret" "nemo_url" {
  secret_id = "nemo-service-url"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "nemo_url_version" {
  secret = google_secret_manager_secret.nemo_url.id
  secret_data = google_cloud_run_v2_service.nemo_service.uri
}

# Grant Agent SA access to this secret
resource "google_secret_manager_secret_iam_member" "agent_nemo_secret" {
  secret_id = google_secret_manager_secret.nemo_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.agent_sa.email}"
}
