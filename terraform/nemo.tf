resource "google_service_account" "nemo_sa" {
  account_id   = "nemo-service-account"
  display_name = "NeMo Service Account"
}

resource "google_project_iam_member" "nemo_vertex_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.nemo_sa.email}"
}

resource "google_cloud_run_v2_service" "nemo" {
  name     = "nemo-service"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.nemo_sa.email

    containers {
      # Use the main image but override the command
      image = "gcr.io/${var.project_id}/financial-advisor:latest"
      command = ["uvicorn", "src.governance.nemo_server:app", "--host", "0.0.0.0", "--port", "8080"]

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
        name  = "OPA_URL"
        value = google_cloud_run_v2_service.opa.uri
      }
    }
  }
  depends_on = [google_cloud_run_v2_service.opa, google_project_service.apis]
}

resource "google_cloud_run_service_iam_member" "nemo_invoker" {
  service  = google_cloud_run_v2_service.nemo.name
  location = google_cloud_run_v2_service.nemo.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
