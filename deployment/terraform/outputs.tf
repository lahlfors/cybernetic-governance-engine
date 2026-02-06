output "gateway_url" {
  description = "The URL of the Gateway Service"
  value       = google_cloud_run_v2_service.gateway.uri
}

output "redis_host" {
  description = "The IP address of the Redis instance"
  value       = google_redis_instance.cache.host
}

output "cluster_endpoint" {
  description = "The IP address of the GKE cluster master"
  value       = google_container_cluster.primary.endpoint
}
