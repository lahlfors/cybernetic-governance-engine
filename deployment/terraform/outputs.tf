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

output "langfuse_s3_bucket_name" {
  description = "GCS Bucket name for Langfuse events"
  value       = google_storage_bucket.langfuse_events.name
}


