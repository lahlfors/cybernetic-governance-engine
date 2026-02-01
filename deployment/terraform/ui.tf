resource "google_cloud_run_v2_service" "ui" {
  name     = "financial-advisor-ui"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      image = "gcr.io/${var.project_id}/financial-advisor-ui:latest"
      ports {
        container_port = 8080
      }
      env {
        name  = "BACKEND_URL"
        value = google_cloud_run_v2_service.backend.uri
      }
    }
  }
  depends_on = [google_cloud_run_v2_service.backend]
}



output "ui_url" {
  value = google_cloud_run_v2_service.ui.uri
}
