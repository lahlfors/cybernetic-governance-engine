resource "google_redis_instance" "cache" {
  name           = "financial-advisor-redis"
  tier           = "BASIC"
  memory_size_gb = 1
  region         = var.region
  redis_version  = "REDIS_7_0"
  display_name   = "Financial Advisor MemoryStore"

  authorized_network = "default"
  connect_mode       = "DIRECT_PEERING"

  depends_on = [google_project_service.apis]
}
