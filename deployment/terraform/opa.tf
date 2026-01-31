resource "google_service_account" "opa_sa" {
  account_id   = "opa-service-account"
  display_name = "OPA Service Account"
}

resource "google_secret_manager_secret_iam_member" "opa_secrets" {
  for_each = toset([
    google_secret_manager_secret.finance_policy.id,
    google_secret_manager_secret.system_authz_policy.id,
    google_secret_manager_secret.opa_config.id,
    google_secret_manager_secret.opa_auth_token.id
  ])
  secret_id = each.key
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.opa_sa.email}"
}

resource "google_cloud_run_v2_service" "opa" {
  name     = "opa-service"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.opa_sa.email

    containers {
      image = "openpolicyagent/opa:0.68.0-static"
      args = [
        "run",
        "--server",
        "--addr=0.0.0.0:8181",
        "--config-file=/config/opa_config.yaml",
        "/policies/finance_policy.rego",
        "/policies/system/system_authz.rego"
      ]
      ports {
        container_port = 8181
      }

      volume_mounts {
        name       = "policy-volume"
        mount_path = "/policies"
      }
      volume_mounts {
        name       = "system-authz-vol"
        mount_path = "/policies/system"
      }
      volume_mounts {
        name       = "opa-config-vol"
        mount_path = "/config"
      }
      volume_mounts {
        name       = "auth-token-vol"
        mount_path = "/secrets/auth"
      }
    }

    volumes {
      name = "policy-volume"
      secret {
        secret = google_secret_manager_secret.finance_policy.secret_id
        items {
          key  = "latest"
          path = "finance_policy.rego"
        }
      }
    }
    volumes {
      name = "system-authz-vol"
      secret {
        secret = google_secret_manager_secret.system_authz_policy.secret_id
        items {
          key  = "latest"
          path = "system_authz.rego"
        }
      }
    }
    volumes {
      name = "opa-config-vol"
      secret {
        secret = google_secret_manager_secret.opa_config.secret_id
        items {
          key  = "latest"
          path = "opa_config.yaml"
        }
      }
    }
    volumes {
      name = "auth-token-vol"
      secret {
        secret = google_secret_manager_secret.opa_auth_token.secret_id
        items {
          key  = "latest"
          path = "token"
        }
      }
    }
  }
  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_service_iam_member" "opa_invoker" {
  service  = google_cloud_run_v2_service.opa.name
  location = google_cloud_run_v2_service.opa.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
