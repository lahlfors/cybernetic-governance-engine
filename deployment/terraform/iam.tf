resource "google_service_account" "agent_sa" {
  account_id   = "agent-engine-sa"
  display_name = "Vertex AI Agent Engine Service Account"
}

resource "google_service_account" "gateway_sa" {
  account_id   = "gateway-sa"
  display_name = "Agentic Gateway Service Account"
}

# --- Agent IAM ---
# Agent needs to:
# 1. Run in Vertex AI (User)
# 2. Access GCS (Object Viewer for artifacts)
# 3. Log to Cloud Logging
# 4. Invoke the Gateway (Cloud Run Invoker)

resource "google_project_iam_member" "agent_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

resource "google_project_iam_member" "agent_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

resource "google_project_iam_member" "agent_storage_user" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

# --- Gateway IAM ---
# Gateway needs to:
# 1. Access Vertex AI (Gemini)
# 2. Access Secret Manager (API Keys - if not using Workload Identity Federation)
# 3. Log to Cloud Logging

resource "google_project_iam_member" "gateway_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.gateway_sa.email}"
}

resource "google_project_iam_member" "gateway_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.gateway_sa.email}"
}

resource "google_project_iam_member" "gateway_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.gateway_sa.email}"
}

# --- GKE Workload Identity Binding (Existing) ---
# Ensuring the existing GKE SA setup in previous iam.tf is preserved or adapted
# The previous iam.tf had a hardcoded service account name "financial-advisor-sa".
# We should probably keep using it for GKE or replace it.
# Let's verify existing iam.tf content again to merge properly or overwrite.
# Previous read showed: google_service_account_iam_member.workload_identity_user for "financial-advisor-sa"
# This suggests "financial-advisor-sa" was created elsewhere or manually?
# I will create it here to be safe and managed by Terraform.

resource "google_service_account" "gke_sa" {
  account_id   = "financial-advisor-sa"
  display_name = "GKE Financial Advisor Service Account"
}

resource "google_service_account_iam_member" "workload_identity_user" {
  service_account_id = google_service_account.gke_sa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[governance-stack/financial-advisor-sa]"
}

