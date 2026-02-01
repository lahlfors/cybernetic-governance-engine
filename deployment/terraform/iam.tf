resource "google_service_account" "financial_advisor" {
  account_id   = "financial-advisor-sa"
  display_name = "Financial Advisor GKE Service Account"
}

resource "google_service_account_iam_member" "workload_identity_user" {
  service_account_id = google_service_account.financial_advisor.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[governance-stack/financial-advisor-sa]"
}
