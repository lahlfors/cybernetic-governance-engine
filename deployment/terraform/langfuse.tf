# Define Service Account for Langfuse
resource "google_service_account" "langfuse_sa" {
  account_id   = "langfuse-sa"
  display_name = "Langfuse Service Account"
}

# Grant Cloud SQL Client role
resource "google_project_iam_member" "langfuse_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.langfuse_sa.email}"
}

# Grant Secret Accessor role
resource "google_project_iam_member" "langfuse_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.langfuse_sa.email}"
}

# --- Secrets Generation ---

resource "random_id" "nextauth_secret" {
  byte_length = 32
}

resource "random_id" "salt" {
  byte_length = 32
}

resource "random_id" "encryption_key" {
  byte_length = 32
}

# --- Secrets Storage ---

resource "google_secret_manager_secret" "database_url" {
  secret_id = "langfuse-database-url"
  replication {
    automatic = true
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "database_url_version" {
  secret = google_secret_manager_secret.database_url.id
  # Construct connection string for Cloud SQL Proxy or Public IP
  # NOTE: Cloud Run with Cloud SQL integration connects via Unix socket at /cloudsql/INSTANCE_CONNECTION_NAME
  secret_data = "postgresql://${google_sql_user.langfuse_user.name}:${random_password.db_password.result}@localhost/${google_sql_database.langfuse_db.name}?host=/cloudsql/${google_sql_database_instance.langfuse_instance.connection_name}"
}

resource "google_secret_manager_secret" "nextauth_secret" {
  secret_id = "langfuse-nextauth-secret"
  replication {
    automatic = true
  }
  depends_on = [google_project_service.apis]
}
resource "google_secret_manager_secret_version" "nextauth_secret_version" {
  secret = google_secret_manager_secret.nextauth_secret.id
  secret_data = random_id.nextauth_secret.hex
}

resource "google_secret_manager_secret" "salt" {
  secret_id = "langfuse-salt"
  replication {
    automatic = true
  }
  depends_on = [google_project_service.apis]
}
resource "google_secret_manager_secret_version" "salt_version" {
  secret = google_secret_manager_secret.salt.id
  secret_data = random_id.salt.hex
}

resource "google_secret_manager_secret" "encryption_key" {
  secret_id = "langfuse-encryption-key"
  replication {
    automatic = true
  }
  depends_on = [google_project_service.apis]
}
resource "google_secret_manager_secret_version" "encryption_key_version" {
  secret = google_secret_manager_secret.encryption_key.id
  secret_data = random_id.encryption_key.hex
}

# --- Cloud Run Service ---

resource "google_cloud_run_v2_service" "langfuse" {
  name     = "langfuse-server"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.langfuse_sa.email

    scaling {
      max_instance_count = 10
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.langfuse_instance.connection_name]
      }
    }

    containers {
      image = "langfuse/langfuse:latest"

      ports {
        container_port = 3000
      }

      resources {
        limits = {
          cpu    = "1000m"
          memory = "2Gi"
        }
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "NEXTAUTH_SECRET"
        value_source {
          secret_key_ref {
            secret = google_secret_manager_secret.nextauth_secret.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "SALT"
        value_source {
          secret_key_ref {
            secret = google_secret_manager_secret.salt.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "ENCRYPTION_KEY"
        value_source {
          secret_key_ref {
            secret = google_secret_manager_secret.encryption_key.secret_id
            version = "latest"
          }
        }
      }

      # Environment Configuration
      env {
        name  = "NEXTAUTH_URL"
        # Since we don't know the URL beforehand, Cloud Run allows updating it later OR relying on HOST header?
        # Langfuse typically needs this.
        # We can use a placeholder or handle it post-deployment.
        # Actually, for Cloud Run v2 (declarative), the URL is predictable if we use custom domains,
        # otherwise it's generated.
        # Workaround: Use a placeholder and update it via a script OR use a fixed custom domain if available.
        # For simplicity in this plan, we might need a post-deploy step to update it.
        # However, for initial deployment, let's just set a dummy value and rely on `deploy_sw.py` to fix it?
        # Or even better: If we use Cloud Run Domain Mapping.
        value = "https://placeholder-url"
      }
      env {
        name  = "TELEMETRY_ENABLED"
        value = "false"
      }
      env {
        name  = "LANGFUSE_ENABLE_EXPERIMENTAL_FEATURES"
        value = "true"
      }
    }
  }

  depends_on = [
    google_project_service.apis,
    google_secret_manager_secret_version.database_url_version
  ]
}

resource "google_cloud_run_service_iam_member" "public_access" {
  location = google_cloud_run_v2_service.langfuse.location
  service  = google_cloud_run_v2_service.langfuse.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
