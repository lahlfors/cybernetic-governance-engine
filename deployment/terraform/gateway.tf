resource "google_cloud_run_v2_service" "gateway" {
  name     = "gateway-service"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL" # Agent Engine (Google Tenant) needs to reach it
  deletion_protection = false

  template {
    service_account = google_service_account.gateway_sa.email

    containers {
      image = var.gateway_image

      resources {
        limits = {
          cpu    = "1000m"
          memory = "512Mi"
        }
      }

      ports {
        container_port = 8080
        name           = "h2c" # Enable HTTP/2 for gRPC
      }

      command = ["python", "-m", "src.gateway.server.main"]

      env {
        name = "VLLM_ENDPOINT"
        # Accessing GKE Internal Service via KubeDNS style name only works if using Direct VPC Egress
        # AND Cloud DNS is configured for GKE Cluster.
        # Otherwise, we might need the internal IP.
        # For now, let's assume we can inject the IP later or use a stable internal DNS if configured.
        value = "http://vllm-inference.governance-stack.svc.cluster.local:8000"
      }

      env {
        name  = "StartMode"
        value = "GATEWAY"
      }
    }

    vpc_access {
      # Direct VPC Egress to access GKE Pod/Service IPs
      network_interfaces {
        network    = "default"
        subnetwork = "default"
      }
      egress = "ALL_TRAFFIC"
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image, # Managed by deploy script
    ]
  }
}

# Bind Agent SA as Invoker
resource "google_cloud_run_service_iam_member" "agent_invoker" {
  location = google_cloud_run_v2_service.gateway.location
  service  = google_cloud_run_v2_service.gateway.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.agent_sa.email}"
}
