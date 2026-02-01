output "opa_url" {
  value = google_cloud_run_v2_service.opa.uri
}



output "gateway_url" {
  value = google_cloud_run_v2_service.gateway_service.uri
}
