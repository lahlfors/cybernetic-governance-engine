
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
        # Check if Terraform managed - if so, we expect it to exist or fail
        tf_managed = config.get("args", {}).get("tf_managed", False)
        if tf_managed:
            print(f"❌ Error: GKE cluster '{cluster_name}' not found, but deployment is Terraform managed.")
            print("   Ensure Terraform has successfully provisioned the cluster.")
            raise RuntimeError("Cluster not found in TF-managed mode")

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
            "--master-ipv4-cidr", "172.16.101.0/28", # Updated to avoid conflict with legacy subnet
            "--enable-ip-alias", # Required for private
            "--enable-master-authorized-networks",
            "--master-authorized-networks", "0.0.0.0/0",
            # Addons: Base defaults + NodeLocalDNS (avoiding separate update step)
            "--addons", "HttpLoadBalancing,HorizontalPodAutoscaling,NodeLocalDNS",
            # Maintenance Window (Daily at 08:00 UTC)
            "--maintenance-window", "08:00"
        ]

        if cluster_conf.get("spot"):
             print("💰 Using Spot VMs (Preemptible) for cost savings...")
             cmd.append("--spot")

        run_command(cmd)

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
        # Default GPU is managed by ensure_gke_cluster.
        # We assume the user has provisioned the correct resources.
        return

    # If we had other accelerators like TPU, logic would go here.
    print(f"⚠️ Unknown or unsupported accelerator: {accelerator}")


def deploy_model_storage(project_id, config):
    """
    Deploys PVC and runs Model Downloader Job for both Fast and Reasoning models.
    """
    print("\n--- 💾 Deploying Model Storage ---")
    
    # Identify models
    models = {
        "fast": config.get("model", {}).get("name", os.environ.get("MODEL_FAST", "Qwen/Qwen2.5-7B-Instruct")),
        "reasoning": os.environ.get("MODEL_REASONING", "casperhansen/deepseek-r1-distill-qwen-32b-awq")
    }

    for key, model_name in models.items():
        if not model_name:
            continue
            
        print(f"\n🔹 Processing Storage for [{key}]: {model_name}")
        
        # Sanitize for K8s resource name
        model_name_sanitized = model_name.lower().replace("/", "-").replace("_", "-").replace(".", "-")
        pvc_name = f"model-cache-{key}-pvc"
        
        # 1. Apply PVC (Unique per model type/key to avoid RWO conflicts if on different nodes)
        pvc_tpl = Path("deployment/k8s/model-pvc.yaml.tpl")
        if not pvc_tpl.exists():
            # Fallback to static if tpl doesn't exist (legacy), but we prefer TPL
            pvc_tpl = Path("deployment/k8s/model-pvc.yaml")
        
        if pvc_tpl.exists():
            with open(pvc_tpl) as f:
                pvc_content = f.read()
            
            # Simple template replacement
            pvc_content = pvc_content.replace("${MODEL_KEY}", key)
            # If using static file without placeholders, it might fail if we don't rename metadata.name
            # But we created model-pvc.yaml.tpl with ${MODEL_KEY} placeholder specific for this.
            
            gen_pvc = Path(f"deployment/k8s/generated/{pvc_name}.yaml")
            gen_pvc.parent.mkdir(parents=True, exist_ok=True)
            with open(gen_pvc, "w") as f:
                f.write(pvc_content)
                
            run_command(["kubectl", "apply", "-f", str(gen_pvc)])
            print(f"✅ PVC {pvc_name} applied.")
        else:
            print(f"⚠️ PVC template not found.")

        # 2. Check Job status
        job_name = f"model-downloader-{model_name_sanitized}"
        res = run_command(
            ["kubectl", "get", "job", job_name, "-n", "governance-stack", "-o", "jsonpath='{.status.succeeded}'"], 
            check=False, capture_output=True
        )
        
        if res.returncode == 0 and res.stdout.strip() == "'1'":
            print(f"✅ Downloader job {job_name} already succeeded.")
            continue

        print(f"⬇️  Initiating download for: {model_name}")
        
        # 3. Generate Job
        tpl_path = Path("deployment/k8s/model-downloader.yaml.tpl")
        if tpl_path.exists():
            with open(tpl_path) as f:
                content = f.read()
            
            content = content.replace("${MODEL_ID}", model_name)
            content = content.replace("${MODEL_NAME_SANITIZED}", model_name_sanitized)
            # Function to replace PVC name in job template? 
            # The job template currently uses claimName: model-cache-pvc (hardcoded)
            # We need to make job template use dynamic PVC name too.
            # Assuming we update template to use ${PVC_NAME} or we replace it here.
            content = content.replace("claimName: model-cache-pvc", f"claimName: {pvc_name}")
            
            gen_job = Path(f"deployment/k8s/generated/model-downloader-{key}.yaml")
            with open(gen_job, "w") as f:
                f.write(content)
                
            run_command(["kubectl", "apply", "-f", str(gen_job)])
            print(f"🚀 Job {job_name} submitted.")
            
            # Wait for completion? Maybe just for the first one or logic to wait later.
            # For now, let's wait to ensure safety as per original design.
            print("⏳ Waiting for download...")
            try:
                run_command([
                    "kubectl", "wait", "--for=condition=complete", 
                    f"job/{job_name}", "-n", "governance-stack", "--timeout=600s"
                ])
                print("✅ Download finished.")
            except Exception:
                print("⚠️ Download timed out. Check logs.")



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
    # Default to gpu
    accelerator_kind = "gpu"

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

    # Deploy Model Storage (PVC + Downloader)
    # deploy_model_storage(project_id, config) # Disabled for Run:ai Streamer

    # Deploy Redis (StatefulSet)
    redis_manifest = k8s_dir / "redis-statefulset.yaml"
    if redis_manifest.exists():
        print(f"📦 Deploying Redis from {redis_manifest}...")
        run_command(["kubectl", "apply", "-f", str(redis_manifest)])
    else:
        print(f"⚠️ Redis manifest not found at {redis_manifest}. Skipping Redis deployment.")

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

    # Apply Static PDB if exists (Hardening)
    pdb_path = k8s_dir / "vllm-pdb.yaml"
    if pdb_path.exists():
        print("🛡️ Applying vLLM Pod Disruption Budget...")
        run_command(["kubectl", "apply", "-f", str(pdb_path)])
        
    # Deploy Reasoning Model (Static Manifest for now, but needs to be applied)
    if os.environ.get("MODEL_REASONING"):
        reasoning_path = k8s_dir / "vllm-reasoning.yaml"
        if reasoning_path.exists():
            print("🧠 Deploying Reasoning Model...")
            # We might need to substitute env vars or other things if it was a template
            # For now it's static, so just apply. 
            run_command(["kubectl", "apply", "-f", str(reasoning_path)])

    
    # 7. Deploy Autoscaling
    deploy_autoscaling(project_id, config)

    print("✅ K8s manifests applied.")


def deploy_autoscaling(project_id, config):
    """
    Deploys KEDA ScaledObjects for vLLM services.
    """
    print("\n--- 📈 Deploying Autoscaling (KEDA) ---")
    k8s_dir = Path("deployment/k8s")
    
    # 1. ScaledObject for Fast Model
    scaler_fast = k8s_dir / "vllm-inference-scaler-draft.yaml"
    if scaler_fast.exists():
        with open(scaler_fast) as f:
            content = f.read()
        content = content.replace("${PROJECT_ID}", project_id)
        
        gen_path = k8s_dir / "generated/vllm-inference-scaler.yaml"
        gen_path.parent.mkdir(parents=True, exist_ok=True)
        with open(gen_path, "w") as f:
            f.write(content)
            
        print("⚡ Applying ScaledObject for Fast Model...")
        run_command(["kubectl", "apply", "-f", str(gen_path)])
        
    # 2. ScaledObject for Reasoning Model
    scaler_reasoning = k8s_dir / "vllm-reasoning-scaler-draft.yaml"
    if scaler_reasoning.exists():
        # Reasoning uses Prometheus by default in draft, no substitution needed yet but good practice
        print("🧠 Applying ScaledObject for Reasoning Model...")
        run_command(["kubectl", "apply", "-f", str(scaler_reasoning)])
        
    print("✅ Autoscaling configured.")
