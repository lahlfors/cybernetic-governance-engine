resource "google_container_cluster" "primary" {
  name     = "governance-cluster"
  location = var.zone

  deletion_protection = false

  remove_default_node_pool = true
  initial_node_count       = 1
  node_config {
    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }
  }

  network    = "default"
  subnetwork = "default"

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.101.0/28"
  }

  ip_allocation_policy {
    # Auto-allocation
    cluster_ipv4_cidr_block  = ""
    services_ipv4_cidr_block = ""
  }

  master_authorized_networks_config {
    cidr_blocks {
      cidr_block   = "0.0.0.0/0"
      display_name = "Allow All"
    }
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }
}

# 1. General Purpose Node Pool (System + Lightweight Apps)
resource "google_container_node_pool" "general_pool" {
  name       = "general-pool"
  location   = var.zone
  cluster    = google_container_cluster.primary.name
  node_count = 1

  autoscaling {
    min_node_count = 1
    max_node_count = 5
  }

  node_config {
    machine_type = "e2-standard-4" # Cost-effective general purpose

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }
  }
}

# 2. GPU Node Pool (Dedicated for vLLM Inference)
resource "google_container_node_pool" "gpu_pool" {
  name       = "gpu-pool"
  location   = var.zone
  cluster    = google_container_cluster.primary.name
  node_count = 1

  autoscaling {
    min_node_count = 0 # Scale to zero if no inference needed (optional cost saving)
    max_node_count = 2
  }

  node_config {
    machine_type = var.machine_type # Default: g2-standard-8 (L4)

    # Standardization: Use Spot VMs for Cost Efficiency (L4 GPU Pattern)
    spot = true

    # Enable Image Streaming (Phase 2: Eliminate Latency)
    gcfs_config {
      enabled = true
    }

    # Use Local SSD for ephemeral storage (Phase 2: Eliminate Latency)
    ephemeral_storage_local_ssd_config {
      local_ssd_count = 1
    }

    # Taint the node so only pods that tolerate it can schedule here
    taint {
      key    = "nvidia.com/gpu"
      value  = "present"
      effect = "NO_SCHEDULE"
    }

    guest_accelerator {
      type  = var.gpu_type
      count = var.gpu_count

      gpu_driver_installation_config {
        gpu_driver_version = "LATEST"
      }

      # Phase 2: GPU Time-Sharing for higher density
      gpu_sharing_config {
        gpu_sharing_strategy       = "TIME_SHARING"
        max_shared_clients_per_gpu = 8
      }
    }

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }
  }
}
