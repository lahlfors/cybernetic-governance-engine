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
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml

# Ensure project root is in sys.path so we can import 'deployment'
# This allows running the script from project root or deployment/ directory
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# Import modularized components
from deployment.lib.utils import load_dotenv, run_command, check_tool_availability
from deployment.lib.gcp import enable_apis, get_redis_host, create_secret
from deployment.lib.k8s import deploy_k8s_infra
from deployment.lib.config import load_config, merge_args_into_config

# Load env immediately
load_dotenv()


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


# --- Hybrid Deployment Logic ---

def deploy_hybrid(project_id, region, image_uri, redis_host, redis_port, config):
    """
    Orchestrates Hybrid Deployment:
    1. Deploys vLLM Infrastructure to GKE.
    2. Mirrors Secrets to K8s.
    3. Deploys Backend to GKE.
    4. Retrieves Backend External IP.
    5. Deploys UI to Cloud Run pointed at Backend IP.
    """
    accelerator = config.get("args", {}).get("accelerator", "gpu")
    print(f"\n--- 🌐 Starting Hybrid Deployment (GKE + Cloud Run) [Accelerator: {accelerator}] ---")
    
    # 1. Deploy GKE Infrastructure (vLLM)
    deploy_k8s_infra(project_id, config)
    
    # 2. Create Secrets in K8s (Mirror from Secret Manager or File)
    # Critical: Do this BEFORE Backend deployment to avoid CrashLoopBackOff for OPA.
    print("\n--- 🔑 Mirroring Secrets to K8s ---")
    
    # OPA Config
    if Path("deployment/opa_config.yaml").exists():
        subprocess.run("kubectl create secret generic opa-configuration --from-file=opa_config.yaml=deployment/opa_config.yaml -n governance-stack --dry-run=client -o yaml | kubectl apply -f -", shell=True)

    # Finance Policy
    policy_path = "src/governed_financial_advisor/governance/policy/finance_policy.rego"
    if not os.path.exists(policy_path) and os.path.exists("deployment/finance_policy.rego"):
         policy_path = "deployment/finance_policy.rego"
         
    subprocess.run(f"kubectl create secret generic finance-policy-rego --from-file=finance_policy.rego={policy_path} -n governance-stack --dry-run=client -o yaml | kubectl apply -f -", shell=True)

    # 3. Deploy Backend to GKE
    print("\n--- ☸️ Deploying Backend to GKE ---")
    deployment_tpl = Path("deployment/k8s/backend-deployment.yaml.tpl")
    if not deployment_tpl.exists():
        print(f"❌ Backend manifest template not found at {deployment_tpl}")
        sys.exit(1)
        
    with open(deployment_tpl) as f:
        manifest_content = f.read()
        
    # Substitute Variables
    timestamp = str(int(time.time()))
    
    manifest_content = manifest_content.replace("${IMAGE_URI}", image_uri)
    manifest_content = manifest_content.replace("${REDIS_HOST}", redis_host or "redis-master")
    manifest_content = manifest_content.replace("${PROJECT_ID}", project_id)
    manifest_content = manifest_content.replace("${REGION}", region)
    manifest_content = manifest_content.replace("${DEPLOY_TIMESTAMP}", timestamp)
    
    # Write to generated/ directory
    generated_dir = Path("deployment/k8s/generated")
    generated_dir.mkdir(parents=True, exist_ok=True)
    generated_file = generated_dir / "backend-deployment.yaml"
    
    with open(generated_file, 'w') as f:
        f.write(manifest_content)
        
    print(f"📄 Generated manifest at: {generated_file}")
    
    # Apply Manifest
    run_command(["kubectl", "apply", "-f", str(generated_file)])
    print("✅ Backend manifest applied.")
    
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
        print("   Proceeding assuming manual URL configuration or failure.")
    
    # 5. Deploy UI to Cloud Run
    if backend_url:
        deploy_ui_service(project_id, region, "financial-advisor-ui", backend_url)

# --- Main Execution Flow ---

def main():
    parser = argparse.ArgumentParser(
        description="Deploy Financial Advisor to Cloud Run & GKE"
    )
    # Defaults from Environment
    default_project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    default_region = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    default_model = os.environ.get("VLLM_MODEL")

    parser.add_argument("--project-id", default=default_project, help="Google Cloud Project ID")
    parser.add_argument("--region", default=default_region, help="Cloud Run Region")
    parser.add_argument("--zone", help="GKE Cluster Zone (optional, overrides region for GKE)")
    parser.add_argument("--service-name", default="governed-financial-advisor", help="Cloud Run Service Name")

    # Build/Deploy Skip Flags
    parser.add_argument("--skip-build", action="store_true", help="Skip image build step")
    parser.add_argument("--skip-redis", action="store_true", help="Skip Redis provisioning")
    parser.add_argument("--skip-ui", action="store_true", help="Skip UI service deployment")
    parser.add_argument("--skip-k8s", action="store_true", help="Skip Kubernetes deployment")

    # Override Arguments
    parser.add_argument("--redis-host", help="Use existing Redis Host")
    parser.add_argument("--redis-port", help="Redis Port")
    parser.add_argument("--redis-instance-name", default="financial-advisor-redis", help="Name for auto-provisioned Redis")
    parser.add_argument("--ui-service-name", default="financial-advisor-ui", help="Cloud Run UI Service Name")
    parser.add_argument("--target", choices=["cloud_run", "hybrid", "gke"], help="Deployment target")

    # New Argument for Accelerator Support
    parser.add_argument("--accelerator", choices=["gpu", "tpu"], help="Inference accelerator type (gpu=H100/NVIDIA, tpu=v5e/Google)")
    parser.add_argument("--accelerator-type", choices=["t4", "tpu", "a100", "l4"], help="GPU Accelerator Type")
    parser.add_argument("--model", default=default_model, help="Hugging Face Model ID")
    parser.add_argument("--quantization", help="Model Quantization (gptq, awq, or none)")
    parser.add_argument("--spot", action="store_true", help="Use Spot VMs for GKE nodes")

    args = parser.parse_args()

    if not args.project_id:
        print("❌ Error: --project-id is required (or GOOGLE_CLOUD_PROJECT env var).")
        sys.exit(1)

    # Load Config
    config = load_config()
    config = merge_args_into_config(config, args)
    
    # Store raw args for legacy access if needed
    config["args"] = vars(args)

    # Inject Model into Config (Crucial for Renderer)
    if args.model:
        config.setdefault("model", {})["name"] = args.model
    if args.quantization:
         config.setdefault("model", {})["quantization"] = args.quantization

    project_id = args.project_id
    
    # Resolution Priority: CLI Args -> Config -> Default
    region = args.region or config.get("project", {}).get("region") or "us-central1"
    
    # Update config with resolved region if it was missing (for consistency)
    if not config.get("project", {}).get("region"):
        config.setdefault("project", {})["region"] = region
      
    print(f"🌍 Target Region: {region}")

    # 0. Enable APIs
    enable_apis(project_id)

    # Clean up generated manifests from previous runs
    generated_dir = Path("deployment/k8s/generated")
    if generated_dir.exists():
        shutil.rmtree(generated_dir)
    generated_dir.mkdir(parents=True, exist_ok=True)

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

    # 2. Secret Management
    print("\n--- 🔑 Managing Secrets ---")

    # Random Auth Token
    token = secrets.token_urlsafe(32)
    create_secret(project_id, "opa-auth-token", literal_value=token)

    # System Authz Policy
    create_secret(project_id, "system-authz-policy", file_path="deployment/system_authz.rego")

    # Finance Policy - Strict Check (No Mocks)
    policy_path = "src/governed_financial_advisor/governance/policy/finance_policy.rego"
    if not os.path.exists(policy_path):
        # Fallback to local deployment/ folder if src/ is missing (e.g. in some build contexts)
        if os.path.exists("deployment/finance_policy.rego"):
             policy_path = "deployment/finance_policy.rego"
        else:
            print(f"❌ Critical Error: Finance Policy not found at {policy_path}")
            print("   Ensure 'src/governed_financial_advisor/governance/policy/finance_policy.rego' exists.")
            sys.exit(1)

    print(f"📄 Using Finance Policy from: {policy_path}")
    create_secret(project_id, "finance-policy-rego", file_path=policy_path)

    # OPA Config
    create_secret(project_id, "opa-configuration", file_path="deployment/opa_config.yaml")

    # 3. Kubernetes Infrastructure (vLLM)
    if not args.skip_k8s:
        if args.target == "cloud_run":
             pass
    else:
        print("\n--- ⏭️ Skipping K8s deployment (--skip-k8s flag set) ---")

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
             # Pass config instead of args
             deploy_hybrid(project_id, region, image_uri, redis_host, redis_port, config)
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

    finally:
        os.remove(temp_path)

if __name__ == "__main__":
    main()
