output "agent_engine_id" {
  value = google_vertex_ai_reasoning_engine.agent.name
}

output "opa_url" {
  value = google_cloud_run_v2_service.opa.uri
}

output "nemo_url" {
  value = google_cloud_run_v2_service.nemo.uri
}

output "gateway_url" {
  value = google_cloud_run_v2_service.gateway_service.uri
}
