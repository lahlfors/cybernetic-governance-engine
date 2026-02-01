resource "null_resource" "app_deployment" {
  triggers = {
    # Trigger on any change to the deployment script or backend templates
    script_sha = sha256(file("../../deployment/deploy_sw.py"))
    tpl_sha    = sha256(file("../../deployment/k8s/backend-deployment.yaml.tpl"))

    # Also trigger if infra changes (e.g. redis IP changes)
    redis_host = google_redis_instance.cache.host
    cluster    = google_container_cluster.primary.endpoint
  }

  depends_on = [
    google_container_node_pool.general_pool,
    google_container_node_pool.gpu_pool,
    google_redis_instance.cache,
    google_secret_manager_secret_version.system_authz_version,
    google_secret_manager_secret_version.finance_policy_version,
    google_secret_manager_secret_version.opa_config_version
  ]

  provisioner "local-exec" {
    working_dir = "${path.module}/../../"
    command = <<EOT
      python3 deployment/deploy_sw.py \
        --project-id ${var.project_id} \
        --region ${var.region} \
        --zone ${var.zone} \
        --redis-host ${google_redis_instance.cache.host} \
        --redis-port ${google_redis_instance.cache.port} \
        --cluster-name ${google_container_cluster.primary.name} \
        --tf-managed \
        --skip-build
    EOT
  }
}
