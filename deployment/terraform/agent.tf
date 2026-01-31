# Use local-exec to trigger the preparation script with the correct URLs
resource "null_resource" "prepare_agent" {
  triggers = {
    nemo_url = google_cloud_run_v2_service.nemo.uri
    opa_url  = google_cloud_run_v2_service.opa.uri
    opa_auth_token = var.opa_auth_token
    project_id = var.project_id
    region = var.region
    always_run = "${timestamp()}"
  }

  provisioner "local-exec" {
    command = "python3 ${path.module}/../scripts/prepare_agent.py --nemo-url=${google_cloud_run_v2_service.nemo.uri} --opa-url=${google_cloud_run_v2_service.opa.uri} --opa-auth-token=${var.opa_auth_token} --project-id=${var.project_id} --location=${var.region}"
  }

  depends_on = [google_cloud_run_v2_service.nemo, google_cloud_run_v2_service.opa]
}

resource "google_storage_bucket_object" "requirements_txt" {
  name   = "requirements.txt"
  bucket = google_storage_bucket.agent_artifacts.name
  source = "${path.module}/../requirements.txt"
  depends_on = [null_resource.prepare_agent]
}

resource "google_storage_bucket_object" "agent_pkl" {
  name   = "agent.pkl"
  bucket = google_storage_bucket.agent_artifacts.name
  source = "${path.module}/../agent.pkl"
  depends_on = [null_resource.prepare_agent]
}

resource "google_storage_bucket_object" "dependencies_tar_gz" {
  name   = "dependencies.tar.gz"
  bucket = google_storage_bucket.agent_artifacts.name
  source = "${path.module}/../dependencies.tar.gz"
  depends_on = [null_resource.prepare_agent]
}

resource "google_vertex_ai_reasoning_engine" "agent" {
  display_name = "governed-financial-advisor"
  project      = var.project_id
  location     = var.region
  description  = "Governed Financial Advisor Agent"

  spec {
    agent_framework = "google-adk"

    package_spec {
      pickle_object_gcs_uri    = "gs://${google_storage_bucket.agent_artifacts.name}/${google_storage_bucket_object.agent_pkl.name}"
      dependency_files_gcs_uri = "gs://${google_storage_bucket.agent_artifacts.name}/${google_storage_bucket_object.dependencies_tar_gz.name}"
      requirements_gcs_uri     = "gs://${google_storage_bucket.agent_artifacts.name}/${google_storage_bucket_object.requirements_txt.name}"
      python_version           = "3.12"
    }
  }
  depends_on = [google_project_service.apis]
}
