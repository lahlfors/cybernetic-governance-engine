resource "google_cloud_run_v2_service" "backend" {
  name     = "financial-advisor-backend"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      image = "gcr.io/${var.project_id}/financial-advisor:latest"
      command = ["python", "src/server.py"]
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
        name  = "AGENT_ENGINE_ID"
        value = google_vertex_ai_reasoning_engine.agent.resource_name
      }
      env {
        name  = "NEMO_URL"
        value = google_cloud_run_v2_service.nemo.uri
      }
    }
  }
  depends_on = [google_vertex_ai_reasoning_engine.agent, google_cloud_run_v2_service.nemo]
}

resource "google_cloud_run_service_iam_member" "backend_invoker" {
  service  = google_cloud_run_v2_service.backend.name
  location = google_cloud_run_v2_service.backend.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "backend_url" {
  value = google_cloud_run_v2_service.backend.uri
}
