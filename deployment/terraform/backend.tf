resource "google_service_account" "backend_sa" {
  account_id   = "financial-advisor-backend-sa"
  display_name = "Financial Advisor Backend SA"
}

resource "google_cloud_run_v2_service" "backend" {
  name     = "financial-advisor-backend"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.backend_sa.email
    containers {
      image = "gcr.io/${var.project_id}/financial-advisor:latest"
      command = ["python", "-m", "src.governed_financial_advisor.server"]
      ports {
        container_port = 8080
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      env {
        name  = "REDIS_HOST"
        value = google_redis_instance.cache.host
      }
      env {
        name  = "REDIS_PORT"
        value = google_redis_instance.cache.port
      }
      resources {
        limits = {
          cpu    = "1"
          memory = "2Gi"
        }
      }
    }
  }
}



output "backend_url" {
  value = google_cloud_run_v2_service.backend.uri
}
