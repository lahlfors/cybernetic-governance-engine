#!/usr/bin/env python3
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Cloud Run & Kubernetes Deployment Script for Governed Financial Advisor

Handles:
1. Google Cloud API enablement.
2. Redis (Memorystore) provisioning/verification.
3. Secret Manager configuration (tokens, OPA policies).
4. Kubernetes Infrastructure (vLLM on GKE).
5. Cloud Run Service Deployment (Main App + Sidecar).
6. UI Service Deployment.

Configuration is read from .env file as the single source of truth.
"""

import argparse
import os
import secrets
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

import yaml


# --- Configuration Loading ---

def load_dotenv():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        print(f"📂 Loading config from: {env_path}")
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    # Don't override existing env vars (allow CLI overrides)
                    if key.strip() not in os.environ:
                        os.environ[key.strip()] = value.strip()
    else:
        print(f"⚠️ No .env file found at {env_path}")

load_dotenv()


# --- Helper Functions ---

def run_command(command, check=True, capture_output=False, env=None):
    """
    Runs a shell command and prints the output.

    Args:
        command (list): The command to run.
        check (bool): Whether to raise an exception on failure.
        capture_output (bool): Whether to capture stdout/stderr.
        env (dict): Environment variables to pass.

    Returns:
        subprocess.CompletedProcess or subprocess.CalledProcessError
    """
    print(f"🚀 Running: {' '.join(command)}")
    try:
        result = subprocess.run(
            command,
            check=check,
            capture_output=capture_output,
            text=True,
            env=env or os.environ.copy()
        )
        if capture_output and result.stdout:
            print(result.stdout.strip())
        return result
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running command: {e}")
        if capture_output and e.stderr:
            print(f"Error details: {e.stderr}")
        if check:
            sys.exit(1)
        return e

def check_tool_availability(tool_name):
    """Checks if a CLI tool is available in the PATH."""
    return shutil.which(tool_name) is not None


# --- Infrastructure Steps ---

def enable_apis(project_id):
    """Enables necessary Google Cloud APIs."""
    print("\n--- 🛠️ Enabling APIs ---")
    apis = [
        "redis.googleapis.com",
        "aiplatform.googleapis.com",
        "secretmanager.googleapis.com",
        "run.googleapis.com",
        "cloudbuild.googleapis.com",
        "container.googleapis.com" # Required for GKE/Kubectl
    ]
    for api in apis:
        run_command([
            "gcloud", "services", "enable", api, "--project", project_id
        ], check=False)

def get_redis_host(project_id, region, instance_name="financial-advisor-redis"):
    """
    Verifies if a Redis instance exists. If not, creates it.
    Returns the Host IP and Port.
    """
    print(f"\n--- 🗄️ Verifying Redis: {instance_name} ---")

    # Check if exists
    check_cmd = [
        "gcloud", "redis", "instances", "describe", instance_name,
        "--region", region,
        "--project", project_id,
        "--format", "value(host, port)"
    ]

    result = run_command(check_cmd, check=False, capture_output=True)

    if result.returncode == 0:
        output = result.stdout.strip()
        # Output format: "10.0.0.3 6379"
        if output:
            parts = output.split()
            host = parts[0]
            port = parts[1] if len(parts) > 1 else "6379"
            print(f"✅ Found existing Redis at {host}:{port}")
            return host, port

    # Create if not exists
    print(f"⚠️ Redis instance '{instance_name}' not found. Creating new instance (Basic Tier)...")
    print("⏳ This operation may take 10-15 minutes.")

    create_cmd = [
        "gcloud", "redis", "instances", "create", instance_name,
        "--region", region,
        "--project", project_id,
        "--tier", "BASIC",
        "--size", "1",
        "--redis-version", "redis_7_0"
    ]

    run_command(create_cmd)

    # Retrieve details after creation
    result = run_command(check_cmd, check=True, capture_output=True)
    output = result.stdout.strip()
    parts = output.split()
    return parts[0], parts[1]

    print("✅ K8s manifests applied.")


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
        run_command([
            "gcloud", "compute", "routers", "nats", "create", nat_name,
            "--router", router_name,
            "--region", region,
            "--project", project_id,
            "--auto-allocate-nat-external-ips",
            "--nat-all-subnet-ip-ranges"
        ])
    else:
        print(f"✅ NAT {nat_name} exists.")

def ensure_gke_cluster(project_id, region, cluster_name="governance-cluster"):
    """
    Checks for GKE cluster. Creates one if not exists (Standard with GPU pool).
    Configures kubectl context. 
    Handles Org Policies: Private Nodes + Shielded Nodes.
    """
    print(f"\n--- ☸️ Verifying GKE Cluster: {cluster_name} ---")
    
    # Check if exists
    result = run_command([
        "gcloud", "container", "clusters", "describe", cluster_name,
        "--region", region,
        "--project", project_id,
        "--format", "value(status)"
    ], check=False, capture_output=True)
    
    if result.returncode == 0:
        print(f"✅ Found existing GKE cluster: {cluster_name}")
        status = result.stdout.strip()
        if status != "RUNNING":
            print(f"⚠️ Cluster status is {status}. Waiting might be required.")
    else:
        print(f"⚠️ GKE cluster '{cluster_name}' not found. Creating new Private Cluster (Standard, GPU-enabled)...")
        print("⏳ This operation may take 15-20 minutes.")
        
        # Ensure Networking for Private Cluster
        setup_networking(project_id, region)
        
        # Create Private Standard cluster
        run_command([
            "gcloud", "container", "clusters", "create", cluster_name,
            "--region", region,
            "--project", project_id,
            "--num-nodes", "1",
            "--machine-type", "n1-standard-4", # Needed for T4
            "--accelerator", "type=nvidia-tesla-t4,count=1",
            "--disk-size", "50",
            "--scopes", "cloud-platform",
            # Security / Policy Compliance
            "--shielded-secure-boot",
            "--shielded-integrity-monitoring",
            "--enable-private-nodes", 
            "--master-ipv4-cidr", "172.16.100.0/28", # Arbitrary non-overlapping range
            "--enable-ip-alias", # Required for private
            "--enable-master-authorized-networks",
            "--master-authorized-networks", "0.0.0.0/0"
        ])
        
        # Install GPU drivers (daemonset)
        print("🔧 Installing Nvidia Drivers...")
        run_command([
            "gcloud", "container", "clusters", "update", cluster_name,
            "--region", region,
            "--project", project_id,
            "--update-addons=NodeLocalDNS=ENABLED" 
        ], check=False)

    # Get Credentials
    print("🔑 Configuring kubectl credentials...")
    run_command([
        "gcloud", "container", "clusters", "get-credentials", cluster_name,
        "--region", region,
        "--project", project_id
    ])

    # Ensure Namespace
    run_command(["kubectl", "create", "namespace", "governance-stack", "--dry-run=client", "-o", "yaml", "|", "kubectl", "apply", "-f", "-"], check=False)
    # Using shell=True for pipe
    subprocess.run("kubectl create namespace governance-stack --dry-run=client -o yaml | kubectl apply -f -", shell=True, check=False)

def deploy_k8s_infra(project_id, region):
    """
    Deploys Kubernetes manifests for Backend & vLLM.
    Ensures kubectl and Cluster are ready.
    """
    print("\n--- ☸️ Deploying K8s Infrastructure (vLLM) ---")

    if not check_tool_availability("kubectl"):
        install_kubectl()
        
    if not check_tool_availability("kubectl"):
        print("⚠️ 'kubectl' still not found. Skipping K8s deployment.")
        return

    # Ensure Cluster & Auth
    ensure_gke_cluster(project_id, region)

    k8s_dir = Path("deployment/k8s")
    if not k8s_dir.exists():
        print(f"⚠️ K8s directory {k8s_dir} not found. Skipping.")
        return

    # Apply all manifests
    print("🚀 Applying manifests from deployment/k8s/...")
    run_command(["kubectl", "apply", "-f", str(k8s_dir)])
    print("✅ K8s manifests applied.")


# --- Secret Management ---

def check_secret_exists(project_id, secret_name):
    """Checks if a secret exists in Secret Manager."""
    cmd = [
        "gcloud", "secrets", "describe", secret_name,
        "--project", project_id,
        "--format", "value(name)"
    ]
    result = run_command(cmd, check=False, capture_output=True)
    return result.returncode == 0

def create_secret(project_id, secret_name, file_path=None, literal_value=None):
    """Creates or updates a secret in Secret Manager."""
    if not check_secret_exists(project_id, secret_name):
        print(f"🔒 Creating secret: {secret_name}")
        run_command([
            "gcloud", "secrets", "create", secret_name,
            "--project", project_id,
            "--replication-policy", "automatic"
        ])
    else:
        print(f"🔒 Secret {secret_name} exists. Updating version...")

    if file_path:
        run_command([
            "gcloud", "secrets", "versions", "add", secret_name,
            "--project", project_id,
            "--data-file", file_path
        ])
    elif literal_value:
        # Use piping to avoid exposing secret in process list
        subprocess.run(
            [
                "gcloud", "secrets", "versions", "add", secret_name,
                "--project", project_id,
                "--data-file", "-"
            ],
            input=literal_value,
            text=True,
            check=True
        )


# --- Service Deployment ---

def check_service_exists(project_id, region, service_name):
    """Checks if a Cloud Run service exists."""
    cmd = [
        "gcloud", "run", "services", "describe", service_name,
        "--region", region,
        "--project", project_id,
        "--format", "value(status.url)"
    ]
    result = run_command(cmd, check=False, capture_output=True)
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return None

def deploy_ui_service(project_id, region, ui_service_name, backend_url, skip_ui=False):
    """
    Deploys UI service to Cloud Run (default behavior).
    Use skip_ui=True to skip deployment entirely.
    Returns the UI service URL.
    """
    print(f"\n--- 🖥️ Deploying UI Service: {ui_service_name} ---")

    if skip_ui:
        print("⏭️ Skipping UI deployment (--skip-ui flag set)")
        existing_url = check_service_exists(project_id, region, ui_service_name)
        if existing_url:
            print(f"   Existing UI service at: {existing_url}")
            return existing_url
        return None

    ui_dir = Path("ui")
    if not ui_dir.exists():
        print(f"❌ UI directory not found at: {ui_dir}")
        print("   Skipping UI deployment.")
        return None

    ui_image_uri = f"gcr.io/{project_id}/financial-advisor-ui:latest"
    print("\n🏗️ Building UI container image...")
    run_command([
        "gcloud", "builds", "submit",
        "--tag", ui_image_uri,
        "--project", project_id,
        str(ui_dir)
    ])

    print("\n🚀 Deploying UI service to Cloud Run...")
    run_command([
        "gcloud", "run", "deploy", ui_service_name,
        "--image", ui_image_uri,
        "--region", region,
        "--project", project_id,
        "--platform", "managed",
        "--allow-unauthenticated",
        "--set-env-vars", f"BACKEND_URL={backend_url}",
        "--port", "8080",
        "--memory", "512Mi",
        "--cpu", "1"
    ])

    deployed_url = check_service_exists(project_id, region, ui_service_name)
    if deployed_url:
        print(f"✅ UI service deployed at: {deployed_url}")
        return deployed_url

    print("⚠️ UI deployment completed but could not retrieve URL.")
    return None


# --- Main Execution Flow ---

def main():
    parser = argparse.ArgumentParser(
        description="Deploy Financial Advisor to Cloud Run & GKE"
    )
    parser.add_argument("--project-id", required=True, help="Google Cloud Project ID")
    parser.add_argument("--region", default="us-central1", help="Cloud Run Region")
    parser.add_argument("--service-name", default="governed-financial-advisor", help="Cloud Run Service Name")

    # Build/Deploy Skip Flags
    parser.add_argument("--skip-build", action="store_true", help="Skip image build step")
    parser.add_argument("--skip-redis", action="store_true", help="Skip Redis provisioning")
    parser.add_argument("--skip-ui", action="store_true", help="Skip UI service deployment")
    parser.add_argument("--skip-k8s", action="store_true", help="Skip Kubernetes deployment")

    # Override Arguments
    parser.add_argument("--redis-host", help="Use existing Redis Host")
    parser.add_argument("--redis-port", default="6379", help="Redis Port")
    parser.add_argument("--redis-instance-name", default="financial-advisor-redis", help="Name for auto-provisioned Redis")
    parser.add_argument("--ui-service-name", default="financial-advisor-ui", help="Cloud Run UI Service Name")
    parser.add_argument("--target", default="cloud_run", choices=["cloud_run", "hybrid", "gke"], help="Deployment target")

    args = parser.parse_args()

    project_id = args.project_id
    region = args.region

    # 0. Enable APIs
    enable_apis(project_id)

    # 1. Infrastructure Provisioning - Redis
    redis_host = args.redis_host
    redis_port = args.redis_port

    if args.skip_redis:
        print("\n--- ⏭️ Skipping Redis provisioning (--skip-redis flag set) ---")
        if not redis_host:
            print("⚠️ Warning: No Redis host provided. Memory will be ephemeral.")
    elif not redis_host:
        redis_host, redis_port = get_redis_host(project_id, region, args.redis_instance_name)
    else:
        print(f"\n--- 🗄️ Using provided Redis: {redis_host}:{redis_port} ---")

    # 2. Kubernetes Infrastructure (vLLM)
    if not args.skip_k8s:
        deploy_k8s_infra(project_id, region)
    else:
        print("\n--- ⏭️ Skipping K8s deployment (--skip-k8s flag set) ---")


    # 3. Secret Management
    print("\n--- 🔑 Managing Secrets ---")

    # Random Auth Token
    token = secrets.token_urlsafe(32)
    create_secret(project_id, "opa-auth-token", literal_value=token)

    # System Authz Policy
    create_secret(project_id, "system-authz-policy", file_path="deployment/system_authz.rego")

    # Finance Policy - Strict Check (No Mocks)
    policy_path = "src/governance/policy/finance_policy.rego"
    if not os.path.exists(policy_path):
        # Fallback to local deployment/ folder if src/ is missing (e.g. in some build contexts)
        if os.path.exists("deployment/finance_policy.rego"):
             policy_path = "deployment/finance_policy.rego"
        else:
            print(f"❌ Critical Error: Finance Policy not found at {policy_path}")
            print("   Ensure 'src/governance/policy/finance_policy.rego' exists.")
            sys.exit(1)

    print(f"📄 Using Finance Policy from: {policy_path}")
    create_secret(project_id, "finance-policy-rego", file_path=policy_path)

    # OPA Config
    create_secret(project_id, "opa-configuration", file_path="deployment/opa_config.yaml")

    # 4. Build Image
    image_uri = f"gcr.io/{project_id}/financial-advisor:latest"
    if not args.skip_build:
        print("\n--- 🏗️ Building Container Image ---")
        run_command([
            "gcloud", "builds", "submit",
            "--tag", image_uri,
            "--project", project_id,
            "."
        ])
    else:
        print(f"\n--- ⏭️ Skipping Build (Image: {image_uri}) ---")

    # 5. Prepare Service YAML
    print("\n--- 📝 Preparing Service Configuration ---")

    with open("deployment/service.yaml") as f:
        service_config = yaml.safe_load(f)

    # Update Ingress Image and Inject Environment Variables
    containers = service_config["spec"]["template"]["spec"]["containers"]
    for container in containers:
        if container["name"] == "ingress-agent":
            container["image"] = image_uri

            # Environment Variables Injection
            env = container.setdefault("env", [])

            def add_env(k, v):
                for item in env:
                    if item["name"] == k:
                        item["value"] = str(v)
                        return
                env.append({"name": k, "value": str(v)})

            # Inject all deployment envs from .env (single source of truth)
            add_env("REDIS_HOST", redis_host or "")
            add_env("REDIS_PORT", redis_port or "6379")
            add_env("GOOGLE_CLOUD_PROJECT", project_id)
            add_env("GOOGLE_CLOUD_LOCATION", region)
            add_env("GOOGLE_GENAI_USE_VERTEXAI", os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "true"))
            add_env("OPA_URL", os.environ.get("OPA_URL", "http://localhost:8181/v1/data/finance/allow"))

            # vLLM Configuration
            # Default to K8s internal DNS (assumes connectivity via VPC or similar)
            vllm_url = os.environ.get("VLLM_BASE_URL", "http://vllm-service.governance-stack.svc.cluster.local:8000/v1")
            add_env("VLLM_BASE_URL", vllm_url)
            add_env("VLLM_API_KEY", os.environ.get("VLLM_API_KEY", "EMPTY"))

            # Force Cloud Run to create a new revision by injecting a timestamp
            import time
            deploy_timestamp = str(int(time.time()))
            add_env("DEPLOY_TIMESTAMP", deploy_timestamp)

            print(f"✅ Injected Envs: REDIS_HOST={redis_host}, VLLM_BASE_URL={vllm_url}, DEPLOY_TIMESTAMP={deploy_timestamp}")
            break

    # Guarantee Secret Name Consistency
    volumes = service_config["spec"]["template"]["spec"]["volumes"]
    for volume in volumes:
        if volume["name"] == "policy-volume":
            volume["secret"]["secretName"] = "finance-policy-rego"
            break

    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix=".yaml", delete=False) as temp:
        yaml.dump(service_config, temp)
        temp_path = temp.name

    try:
        if args.target == "hybrid" or args.target == "gke":
             deploy_hybrid(project_id, region, image_uri, redis_host, redis_port)
             return

        # 6. Deploy Main Service
        print("\n--- 🚀 Deploying to Cloud Run ---")
        run_command([
            "gcloud", "run", "services", "replace", temp_path,
            "--region", region,
            "--project", project_id
        ])

        # Get the backend URL for UI configuration
        backend_url = check_service_exists(project_id, region, args.service_name)
        if not backend_url:
            backend_url = f"https://{args.service_name}-{project_id}.{region}.run.app"

        print("\n--- ✅ Main Service Deployment Complete ---")
        print(f"Backend URL: {backend_url}")

        # 7. Deploy UI Service
        ui_url = deploy_ui_service(
            project_id,
            region,
            args.ui_service_name,
            backend_url,
            skip_ui=args.skip_ui
        )

        print("\n--- ✅ Full Deployment Complete ---")
        print(f"Backend Service: {backend_url}")
        if ui_url:
            print(f"UI Service: {ui_url}")

        if ui_url:
            print(f"UI Service: {ui_url}")

    finally:
        os.remove(temp_path)

# --- Hybrid Deployment Logic ---

def deploy_hybrid(project_id, region, image_uri, redis_host, redis_port):
    """
    Orchestrates Hybrid Deployment:
    1. Deploys vLLM & Backend to GKE.
    2. Retrieves Backend External IP.
    3. Deploys UI to Cloud Run pointed at Backend IP.
    """
    print("\n--- 🌐 Starting Hybrid Deployment (GKE + Cloud Run) ---")
    
    # 1. Deploy GKE Infrastructure (vLLM)
    deploy_k8s_infra(project_id, region)
    
    # 2. Deploy Backend to GKE
    print("\n--- ☸️ Deploying Backend to GKE ---")
    deployment_file = Path("deployment/k8s/backend-deployment.yaml")
    if not deployment_file.exists():
        print(f"❌ Backend manifest not found at {deployment_file}")
        sys.exit(1)
        
    with open(deployment_file) as f:
        manifest_content = f.read()
        
    # Substitute Variables
    import time
    timestamp = str(int(time.time()))
    
    manifest_content = manifest_content.replace("${IMAGE_URI}", image_uri)
    manifest_content = manifest_content.replace("${REDIS_HOST}", redis_host)
    manifest_content = manifest_content.replace("${PROJECT_ID}", project_id)
    manifest_content = manifest_content.replace("${REGION}", region)
    manifest_content = manifest_content.replace("${DEPLOY_TIMESTAMP}", timestamp)
    
    # Apply Manifest
    with tempfile.NamedTemporaryFile(mode='w', suffix=".yaml", delete=False) as temp:
        temp.write(manifest_content)
        temp_path = temp.name
        
    try:
        run_command(["kubectl", "apply", "-f", temp_path])
        print("✅ Backend manifest applied.")
    finally:
        os.remove(temp_path)
        
    # 3. Create Secrets in K8s (Mirror from Secret Manager or File)
    print("\n--- 🔑 Mirroring Secrets to K8s ---")
    # OPA Config
    if Path("deployment/opa_config.yaml").exists():
        run_command(["kubectl", "create", "secret", "generic", "opa-configuration", 
                     "--from-file=opa_config.yaml=deployment/opa_config.yaml", 
                     "--namespace=governance-stack", "--dry-run=client", "-o", "yaml", "|", "kubectl", "apply", "-f", "-"], check=False) # Pipe needs shell=True or specialized handling, simplifying for now
        # Simplified:
        subprocess.run("kubectl create secret generic opa-configuration --from-file=opa_config.yaml=deployment/opa_config.yaml -n governance-stack --dry-run=client -o yaml | kubectl apply -f -", shell=True)

    # Finance Policy
    policy_path = "src/governance/policy/finance_policy.rego"
    if not os.path.exists(policy_path) and os.path.exists("deployment/finance_policy.rego"):
         policy_path = "deployment/finance_policy.rego"
         
    subprocess.run(f"kubectl create secret generic finance-policy-rego --from-file=finance_policy.rego={policy_path} -n governance-stack --dry-run=client -o yaml | kubectl apply -f -", shell=True)
    
    # 4. Wait for Backend External IP
    print("\n--- ⏳ Waiting for Backend Service External IP ---")
    backend_url = None
    for _ in range(20): # Retry for ~2 minutes
        result = run_command(
            ["kubectl", "get", "service", "governed-financial-advisor", "-n", "governance-stack", "-o", "jsonpath='{.status.loadBalancer.ingress[0].ip}'"],
            check=False, capture_output=True
        )
        ip = result.stdout.strip("'")
        if ip:
            backend_url = f"http://{ip}"
            print(f"✅ Found Backend IP: {ip}")
            break
        print("   Waiting for LoadBalancer IP...")
        time.sleep(10)
        
    if not backend_url:
        print("⚠️ Could not retrieve Backend IP. GKE deployment may be pending. Check 'kubectl get svc -n governance-stack'.")
        # Fallback to internal DNS for testing inside cluster? No, UI is external.
        print("   Proceeding assuming manual URL configuration or failure.")
    
    # 5. Deploy UI to Cloud Run
    if backend_url:
        deploy_ui_service(project_id, region, "financial-advisor-ui", backend_url)

if __name__ == "__main__":
    main()

