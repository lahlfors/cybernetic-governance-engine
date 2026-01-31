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
    google_container_node_pool.primary_nodes,
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
        --redis-host redis-master.governance-stack.svc.cluster.local \
        --redis-port 6379 \
        --cluster-name ${google_container_cluster.primary.name} \
        --tf-managed
    EOT
  }
}
