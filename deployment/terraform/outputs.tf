output "langfuse_url" {
  description = "The URL of the Langfuse Cloud Run service"
  value       = google_cloud_run_v2_service.langfuse.uri
}

output "langfuse_database_instance" {
  description = "The Cloud SQL instance connection name for Langfuse"
  value       = google_sql_database_instance.langfuse_instance.connection_name
}

output "langfuse_public_key" {
  description = "Generated Langfuse Public Key"
  value       = random_id.langfuse_public_key.hex
  sensitive   = true
}

output "langfuse_secret_key" {
  description = "Generated Langfuse Secret Key"
  value       = random_id.langfuse_secret_key.hex
  sensitive   = true
}
