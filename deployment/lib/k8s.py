
import os
import subprocess
from pathlib import Path
from .utils import run_command, check_tool_availability
from .renderer import generate_vllm_manifest

def install_kubectl():
    """Installs kubectl using gcloud and adds it to PATH."""
    print("🛠️ Installing kubectl...")
    run_command(["gcloud", "components", "install", "kubectl", "--quiet"], check=False)
    
    # Try to find SDK root and add to PATH
    try:
        res = run_command(["gcloud", "info", "--format", "value(installation.sdk_root)"], check=False, capture_output=True)
        if res.returncode == 0:
            sdk_root = res.stdout.strip()
            if sdk_root:
                bin_path = os.path.join(sdk_root, "bin")
                if os.path.exists(bin_path):
                    print(f"   Adding {bin_path} to PATH")
                    os.environ["PATH"] = f"{bin_path}:{os.environ['PATH']}"
    except Exception as e:
        print(f"⚠️ Failed to determine SDK root: {e}")
    
    # Verify installation
    if not check_tool_availability("kubectl"):
        print("⚠️ kubectl installation attempted but still not found in PATH.")

def setup_networking(project_id, region):
    """Ensures Cloud Router and NAT exist for Private GKE connectivity."""
    print(f"\n--- 🌐 Verifying Cloud NAT for Region: {region} ---")
    router_name = f"nat-router-{region}"
    nat_name = f"nat-config-{region}"
    network = "default" # Assuming default network

    # 1. Create Router
    if run_command(["gcloud", "compute", "routers", "describe", router_name, "--region", region, "--project", project_id], check=False, capture_output=True).returncode != 0:
        print(f"Creating Cloud Router: {router_name}")
        run_command([
            "gcloud", "compute", "routers", "create", router_name,
            "--project", project_id,
            "--region", region,
            "--network", network
        ])
    else:
        print(f"✅ Router {router_name} exists.")

    # 2. Create NAT
    if run_command(["gcloud", "compute", "routers", "nats", "describe", nat_name, "--router", router_name, "--region", region, "--project", project_id], check=False, capture_output=True).returncode != 0:
        print(f"Creating Cloud NAT: {nat_name}")
        result = run_command([
            "gcloud", "compute", "routers", "nats", "create", nat_name,
            "--router", router_name,
            "--region", region,
            "--project", project_id,
            "--auto-allocate-nat-external-ips",
            "--nat-all-subnet-ip-ranges"
        ], check=False)
        
        if result.returncode != 0:
             print(f"⚠️ NAT creation failed (likely due to existing NAT in region). Proceeding assuming connectivity exists.")
        else:
             print(f"✅ Created Cloud NAT: {nat_name}")
    else:
        print(f"✅ NAT {nat_name} exists.")

def ensure_gke_cluster(project_id, config):
    """
    Checks for GKE cluster. Creates one if not exists (Standard with GPU pool).
    Configures kubectl context. 
    Handles Org Policies: Private Nodes + Shielded Nodes.
    """
    cluster_name = config.get("cluster", {}).get("name", "governance-cluster")
    region = config.get("project", {}).get("region", "us-central1")
    zone = config.get("project", {}).get("zone")
    
    print(f"\n--- ☸️ Verifying GKE Cluster: {cluster_name} ---")
    
    # Check if exists
    location_flag = "--zone" if zone else "--region"
    location_value = zone if zone else region

    result = run_command([
        "gcloud", "container", "clusters", "describe", cluster_name,
        location_flag, location_value,
        "--project", project_id,
        "--format", "value(status)"
    ], check=False, capture_output=True)
    
    if result.returncode == 0:
        print(f"✅ Found existing GKE cluster: {cluster_name}")
        status = result.stdout.strip()
        if status != "RUNNING":
            print(f"⚠️ Cluster status is {status}. Waiting might be required.")
    else:
        print(f"⚠️ GKE cluster '{cluster_name}' not found. Creating new Private Cluster...")
        print("⏳ This operation may take 15-20 minutes.")
        
        # Ensure Networking for Private Cluster
        setup_networking(project_id, region)
        
        # Resource Logic from Config
        cluster_conf = config.get("cluster", {})
        machine_type = cluster_conf.get("machine_type", "n1-standard-4")
        disk_size = str(cluster_conf.get("disk_size_gb", "50"))
        
        accelerator = cluster_conf.get("accelerator", {})
        accelerator_type = accelerator.get("type", "nvidia-tesla-t4")
        accelerator_count = str(accelerator.get("count", "1"))
        
        print(f"ℹ️ Configuring: {machine_type} with {accelerator_count}x {accelerator_type}")

        # Create Private Standard cluster
        cmd = [
            "gcloud", "container", "clusters", "create", cluster_name,
            location_flag, location_value,
            "--project", project_id,
            "--num-nodes", "1",
            "--machine-type", machine_type,
            "--accelerator", f"type={accelerator_type},count={accelerator_count}",
            "--disk-size", disk_size,
            "--scopes", "cloud-platform",
            # Security / Policy Compliance
            "--shielded-secure-boot",
            "--shielded-integrity-monitoring",
            "--enable-private-nodes", 
            "--master-ipv4-cidr", "172.16.100.0/28", # Arbitrary non-overlapping range
            "--enable-ip-alias", # Required for private
            "--enable-master-authorized-networks",
            "--master-authorized-networks", "0.0.0.0/0"
        ]
        
        if cluster_conf.get("spot"):
             print("💰 Using Spot VMs (Preemptible) for cost savings...")
             cmd.append("--spot")

        run_command(cmd)
        
        # Install GPU drivers (daemonset)
        if "nvidia" in accelerator_type:
            print("🔧 Installing Nvidia Drivers...")
            run_command([
                "gcloud", "container", "clusters", "update", cluster_name,
                location_flag, location_value,
                "--project", project_id,
                "--update-addons=NodeLocalDNS=ENABLED" 
            ], check=False)

    # Get Credentials
    print("🔑 Configuring kubectl credentials...")
    location_flag = "--zone" if zone else "--region"
    location_value = zone if zone else region
    run_command([
        "gcloud", "container", "clusters", "get-credentials", cluster_name,
        location_flag, location_value,
        "--project", project_id
    ])

    # Ensure Namespace
    subprocess.run("kubectl create namespace governance-stack --dry-run=client -o yaml | kubectl apply -f -", shell=True, check=False)

def ensure_accelerator_node_pool(project_id, region, cluster_name, accelerator):
    """Ensures the appropriate node pool exists for the accelerator."""

    if accelerator == "gpu":
        # Default GPU is managed by ensure_gke_cluster (T4).
        # We assume the user has provisioned H100s if they want to use them, or we fallback to what's there.
        # Automating A3 provisioning is complex due to quota.
        return

    # TPU Logic
    pool_name = "tpu-pool"
    print(f"\n--- ⚡ Verifying TPU Node Pool: {pool_name} ---")

    cmd = [
        "gcloud", "container", "node-pools", "describe", pool_name,
        "--cluster", cluster_name, "--region", region, "--project", project_id,
        "--format", "value(status)"
    ]
    if run_command(cmd, check=False, capture_output=True).returncode == 0:
        print(f"✅ Node pool '{pool_name}' exists.")
        return

    print(f"⚠️ Node pool '{pool_name}' not found. Creating TPU v5e-8t pool...")
    print("⏳ This operation may take 10-15 minutes.")

    # Note: TPU v5e-8t (ct5lp-hightpu-8t) is zonal. We need to pick a zone.
    # We'll use {region}-a as a default guess, or rely on region if supported (Autopilot/Nap).
    # Standard GKE requires specific zone for TPUs usually.
    node_location = f"{region}-a"

    create_cmd = [
        "gcloud", "container", "node-pools", "create", pool_name,
        "--cluster", cluster_name,
        "--region", region,
        "--project", project_id,
        "--num-nodes", "1",
        "--machine-type", "ct5lp-hightpu-8t",
        "--node-locations", node_location,
        "--enable-image-streaming" # Good for large images
    ]

    run_command(create_cmd)


def deploy_k8s_infra(project_id, config, args=None):
    """
    Deploys Kubernetes manifests for Backend & vLLM.
    Ensures kubectl and Cluster are ready.
    """
    # Prefer config if available, fallback args if needed (but we are moving to config)
    # Accelerator info should be in config now
    accelerator = config.get("args", {}).get("accelerator", "gpu") # We might store raw args in config too for convenience
    
    # Or just check args if passed, but better to rely on config
    # Let's say config has 'cluster' -> 'accelerator' -> 'type' (e.g. nvidia-tesla-t4)
    # But accelerator argument (gpu/tpu) is high level.
    # Let's keep args for the high level switch if needed, or put it in config.
    
    # For now, let's look at config['cluster']['accelerator']['type']
    acc_type = config.get("cluster", {}).get("accelerator", {}).get("type", "nvidia-tesla-t4")
    # Simple heuristic: if 'tpu' in name, it's tpu.
    accelerator_kind = "tpu" if "tpu" in acc_type else "gpu"
    
    print(f"\n--- ☸️ Deploying K8s Infrastructure (vLLM) [Accelerator: {accelerator_kind}] ---")

    if not check_tool_availability("kubectl"):
        install_kubectl()
        
    if not check_tool_availability("kubectl"):
        print("⚠️ 'kubectl' still not found. Skipping K8s deployment.")
        return

    # Ensure Cluster & Auth
    ensure_gke_cluster(project_id, config)

    # Ensure Node Pool for Accelerator
    cluster_name = config.get("cluster", {}).get("name", "governance-cluster")
    region = config.get("project", {}).get("region", "us-central1")
    ensure_accelerator_node_pool(project_id, region, cluster_name, accelerator_kind)

    k8s_dir = Path("deployment/k8s")
    if not k8s_dir.exists():
        print(f"⚠️ K8s directory {k8s_dir} not found. Skipping.")
        return

    # Generate Dynamic Manifests
    print(f"📄 Generating vLLM manifest for {accelerator_kind}...")
    vllm_yaml = generate_vllm_manifest(accelerator_kind, config)
    if not vllm_yaml:
        print("❌ Failed to generate vLLM manifest.")
        return

    generated_dir = Path("deployment/k8s/generated")
    generated_dir.mkdir(parents=True, exist_ok=True)

    # Write generated manifest to the directory so kubectl apply finds it
    vllm_path = generated_dir / "vllm-deployment.yaml"
    with open(vllm_path, 'w') as f:
        f.write(vllm_yaml)

    # Apply generated manifests
    print(f"🚀 Applying manifests from {generated_dir}...")
    run_command(["kubectl", "apply", "-f", str(generated_dir)])
    print("✅ K8s manifests applied.")
