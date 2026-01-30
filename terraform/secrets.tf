resource "google_secret_manager_secret" "opa_auth_token" {
  secret_id = "opa-auth-token"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "opa_auth_token" {
  secret      = google_secret_manager_secret.opa_auth_token.id
  secret_data = var.opa_auth_token
}

resource "google_secret_manager_secret" "finance_policy" {
  secret_id = "finance-policy-rego"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "finance_policy" {
  secret      = google_secret_manager_secret.finance_policy.id
  secret_data = file("${path.module}/../src/governance/policy/finance_policy.rego")
}

resource "google_secret_manager_secret" "system_authz_policy" {
  secret_id = "system-authz-policy"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "system_authz_policy" {
  secret      = google_secret_manager_secret.system_authz_policy.id
  secret_data = file("${path.module}/../deployment/system_authz.rego")
}

resource "google_secret_manager_secret" "opa_config" {
  secret_id = "opa-configuration"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "opa_config" {
  secret      = google_secret_manager_secret.opa_config.id
  secret_data = file("${path.module}/../deployment/opa_config.yaml")
}
