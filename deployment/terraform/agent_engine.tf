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


resource "null_resource" "patch_telemetry" {
  triggers = {
    engine_id = google_vertex_ai_reasoning_engine.financial_advisor.name
    telemetry = var.enable_telemetry
    trace     = var.trace_content
  }

  provisioner "local-exec" {
    command = <<EOT
      python3 ../../deployment/patch_env_vars.py \
        --project-id ${var.project_id} \
        --region ${var.region} \
        --engine-id ${google_vertex_ai_reasoning_engine.financial_advisor.name} \
        --env-vars '{"GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "${var.enable_telemetry}", "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "${var.trace_content}"}'
    EOT
  }
  depends_on = [google_vertex_ai_reasoning_engine.financial_advisor]
}
