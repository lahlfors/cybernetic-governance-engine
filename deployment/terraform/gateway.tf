# 1. Service Accounts
resource "google_service_account" "agent_sa" {
  account_id   = "sa-agent-reasoning"
  display_name = "Agent Service Account (Reasoning Only)"
}

resource "google_service_account" "gateway_sa" {
  account_id   = "sa-gateway-executor"
  display_name = "Gateway Service Account (Execution)"
}

# 2. Gateway Service (Cloud Run)
resource "google_cloud_run_v2_service" "gateway_service" {
  name     = "gateway-service"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY" # Only internal traffic (Mesh/VPC)

  template {
    service_account = google_service_account.gateway_sa.email

    containers {
      image = var.gateway_image

      ports {
        container_port = 8080
        name           = "h2c" # Enable HTTP/2 for gRPC
      }

      env {
        name  = "PORT"
        value = "8080"
      }

      # Resources for Sidecar Pattern (e.g. 1 CPU, 512MB)
      resources {
        limits = {
          cpu    = "1000m"
          memory = "512Mi"
        }
      }
    }
  }
}

# 3. IAM Binding: Allow Agent to Invoke Gateway
resource "google_cloud_run_service_iam_binding" "invoker" {
  location = google_cloud_run_v2_service.gateway_service.location
  service  = google_cloud_run_v2_service.gateway_service.name
  role     = "roles/run.invoker"
  members = [
    "serviceAccount:${google_service_account.agent_sa.email}"
  ]
}
