resource "google_redis_instance" "cache" {
  name           = "financial-advisor-redis"
  memory_size_gb = 1
  region         = var.region
  location_id    = var.zone

  tier = "BASIC"

  redis_version = "REDIS_7_0"
  display_name  = "Financial Advisor Cache"

  authorized_network = "default"
}

output "redis_host" {
  value = google_redis_instance.cache.host
}

output "redis_port" {
  value = google_redis_instance.cache.port
}
