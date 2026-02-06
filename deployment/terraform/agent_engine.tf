resource "google_storage_bucket" "agent_artifacts" {
  name          = "${var.project_id}-agent-artifacts"
  location      = var.region
  force_destroy = true
  uniform_bucket_level_access = true
}

resource "google_storage_bucket_object" "pickle" {
  name   = "reasoning_engine/pickle-${filemd5("../../deployment/artifacts/pickle.pkl")}.pkl"
  bucket = google_storage_bucket.agent_artifacts.name
  source = "../../deployment/artifacts/pickle.pkl"
}

resource "google_storage_bucket_object" "requirements" {
  name   = "reasoning_engine/requirements-${filemd5("../../deployment/artifacts/requirements.txt")}.txt"
  bucket = google_storage_bucket.agent_artifacts.name
  source = "../../deployment/artifacts/requirements.txt"
}

resource "google_storage_bucket_object" "dependencies" {
  name   = "reasoning_engine/dependencies-${filemd5("../../deployment/artifacts/dependencies.tar.gz")}.tar.gz"
  bucket = google_storage_bucket.agent_artifacts.name
  source = "../../deployment/artifacts/dependencies.tar.gz"
}

resource "google_vertex_ai_reasoning_engine" "financial_advisor" {
  provider = google-beta

  display_name = "financial-advisor-engine"
  description  = "Governed Financial Advisor Reasoning Engine"
  project      = var.project_id
  region       = var.region

  spec {
    package_spec {
      pickle_object_gcs_uri = "gs://${google_storage_bucket.agent_artifacts.name}/${google_storage_bucket_object.pickle.name}"
      requirements_gcs_uri  = "gs://${google_storage_bucket.agent_artifacts.name}/${google_storage_bucket_object.requirements.name}"
      dependency_files_gcs_uri = "gs://${google_storage_bucket.agent_artifacts.name}/${google_storage_bucket_object.dependencies.name}"
    }
  }
}

