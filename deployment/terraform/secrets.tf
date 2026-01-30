resource "random_password" "opa_token" {
  length  = 32
  special = false
}

resource "google_secret_manager_secret" "opa_auth_token" {
  secret_id = "opa-auth-token"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "opa_auth_token_version" {
  secret = google_secret_manager_secret.opa_auth_token.id
  secret_data = random_password.opa_token.result
}

# Note: For file-based secrets, we assume the files exist in relative paths
# relative to where `terraform apply` is run (root of repo or deployment/terraform)
# Since we will create a script to run this, we can control CWD.
# Assuming CWD is deployment/terraform, we use ../../ for root files.

resource "google_secret_manager_secret" "system_authz" {
  secret_id = "system-authz-policy"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "finance_policy" {
  secret_id = "finance-policy-rego"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "opa_config" {
  secret_id = "opa-configuration"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

# We only create the secrets container here. 
# Populating file-based secrets via Terraform is tricky if files change often.
# Ideally, Terraform manages them.
# Let's populate them using `file()`.

resource "google_secret_manager_secret_version" "system_authz_version" {
  secret = google_secret_manager_secret.system_authz.id
  secret_data = file("../../deployment/system_authz.rego")
}

resource "google_secret_manager_secret_version" "finance_policy_version" {
  secret = google_secret_manager_secret.finance_policy.id
  secret_data = file("../../src/governed_financial_advisor/governance/policy/finance_policy.rego")
}

resource "google_secret_manager_secret_version" "opa_config_version" {
  secret = google_secret_manager_secret.opa_config.id
  secret_data = file("../../deployment/opa_config.yaml")
}
