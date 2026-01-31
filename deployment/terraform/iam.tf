resource "google_service_account_iam_member" "workload_identity_user" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/financial-advisor-sa@${var.project_id}.iam.gserviceaccount.com"
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[governance-stack/financial-advisor-sa]"
}
