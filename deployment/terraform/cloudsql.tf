resource "random_password" "db_password" {
  length  = 16
  special = false
}

resource "google_sql_database_instance" "langfuse_instance" {
  name                = "langfuse-instance-${var.project_id}"
  database_version    = "POSTGRES_15"
  region              = var.region
  deletion_protection = false

  settings {
    tier = "db-f1-micro"

    ip_configuration {
      ipv4_enabled    = true
      private_network = "projects/${var.project_id}/global/networks/default"
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_sql_database" "langfuse_db" {
  name     = "langfuse"
  instance = google_sql_database_instance.langfuse_instance.name
}

resource "google_sql_user" "langfuse_user" {
  name     = "langfuse"
  instance = google_sql_database_instance.langfuse_instance.name
  password = random_password.db_password.result
}
