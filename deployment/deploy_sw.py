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

# Ensure local kubectl is in PATH
os.environ["PATH"] = os.getcwd() + os.pathsep + os.environ["PATH"]

# Ensure project root is in sys.path so we can import 'deployment'
# This allows running the script from project root or deployment/ directory
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# Import modularized components
from deployment.lib.utils import load_dotenv, run_command
from deployment.lib.k8s import deploy_k8s_infra
from deployment.lib.config import load_config

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


# --- Application Deployment Logic ---

def deploy_application_stack(project_id, region, image_uri, redis_host, redis_port, config, skip_ui=False, cluster_name=None):
    """
    Orchestrates Application Deployment on top of provisions Infrastructure:
    1. Deploys/Updates vLLM Inference Engine (GKE).
    2. Mirrors Secrets from Secret Manager/Env to K8s.
    3. Deploys Backend Service (GKE).
    4. Deploys UI Service (Cloud Run).
    """
    accelerator = config.get("args", {}).get("accelerator", "gpu")
    print(f"\n--- 🚀 Starting Application Deployment [Accelerator: {accelerator}] ---")

    # 1. Deploy vLLM / K8s Base Infra
    # This ensures the cluster is configured and vLLM is running
    deploy_k8s_infra(project_id, config)

    # 2. Redis Configuration
    # We rely on the Redis Host provided by Terraform (Cloud Memorystore)
    # If not provided, we warn/fail rather than trying to provision a toy Redis in K8s (legacy behavior removed)
    if not redis_host:
         print("⚠️ Warning: No Redis Host provided. Application will use ephemeral memory.")
         redis_host = "localhost" # Fallback/Error state

    print(f"ℹ️ Using Redis Host: {redis_host}:{redis_port}")
    
    # 3. Mirror Secrets to K8s
    # We grab secrets that Terraform (or manual setup) put into Secret Manager/Env and ensure K8s has them.
    # TODO: In the future, use External Secrets Operator or CSI Driver.
    print("\n--- 🔑 Mirroring Secrets to K8s ---")
    
    # OPA Config
    if Path("deployment/opa_config.yaml").exists():
        subprocess.run("kubectl create secret generic opa-configuration --from-file=opa_config.yaml=deployment/opa_config.yaml -n governance-stack --dry-run=client -o yaml | kubectl apply -f -", shell=True)

    # Hugging Face Token (Required for vLLM)
    hf_token = os.environ.get("HUGGING_FACE_HUB_TOKEN") or os.environ.get("HF_TOKEN")
    if hf_token:
        subprocess.run(f"kubectl create secret generic hf-token-secret --from-literal=token={hf_token} -n governance-stack --dry-run=client -o yaml | kubectl apply -f -", shell=True)
    else:
        print("⚠️ No HF_TOKEN found. vLLM model download may fail.")

    # Finance Policy
    policy_path = "src/governed_financial_advisor/governance/policy/finance_policy.rego"
    if not os.path.exists(policy_path) and os.path.exists("deployment/finance_policy.rego"):
         policy_path = "deployment/finance_policy.rego"
         
    if os.path.exists(policy_path):
        subprocess.run(f"kubectl create secret generic finance-policy-rego --from-file=finance_policy.rego={policy_path} -n governance-stack --dry-run=client -o yaml | kubectl apply -f -", shell=True)

    # 4. Deploy Backend
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
    manifest_content = manifest_content.replace("${REDIS_HOST}", redis_host)
    manifest_content = manifest_content.replace("${PROJECT_ID}", project_id)
    manifest_content = manifest_content.replace("${REGION}", region)
    vertex_ai_flag = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "1")
    manifest_content = manifest_content.replace("${GOOGLE_GENAI_USE_VERTEXAI}", vertex_ai_flag)
    manifest_content = manifest_content.replace("${DEPLOY_TIMESTAMP}", timestamp)
    
    # Write Generated Manifest
    generated_dir = Path("deployment/k8s/generated")
    generated_dir.mkdir(parents=True, exist_ok=True)
    generated_file = generated_dir / "backend-deployment.yaml"
    
    with open(generated_file, 'w') as f:
        f.write(manifest_content)
        
    print(f"📄 Generated manifest: {generated_file}")
    run_command(["kubectl", "apply", "-f", str(generated_file)])
    print("✅ Backend manifest applied.")
    
    # 5. Wait for LoadBalancer IP
    print("\n--- ⏳ Waiting for Backend IP ---")
    backend_url = None
    for _ in range(30): # 5 Minutes Max
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
        print("⚠️ Failed to retrieve Backend IP via kubectl. Cloud Run UI deployment may fail to connect.")
    
    # 6. Deploy UI
    if backend_url:
        deploy_ui_service(project_id, region, "financial-advisor-ui", backend_url, skip_ui=skip_ui)

# --- Main Execution ---

def main():
    parser = argparse.ArgumentParser(description="Deploy Financial Advisor App (TF Managed Infra)")
    
    # Env Defaults
    default_project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    default_region = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    default_zone = os.environ.get("GOOGLE_CLOUD_ZONE")

    # Core Arguments
    parser.add_argument("--project-id", default=default_project, required=not default_project, help="GCP Project ID")
    parser.add_argument("--region", default=default_region, help="GCP Region")
    parser.add_argument("--zone", default=default_zone, help="GCP Zone")

    # Infrastructure Inputs (Passed from Terraform)
    parser.add_argument("--redis-host", help="Redis Host IP")
    parser.add_argument("--redis-port", default="6379", help="Redis Port")
    parser.add_argument("--cluster-name", help="GKE Cluster Name")
    
    # Operational Flags
    parser.add_argument("--skip-build", action="store_true", help="Skip Docker build")
    parser.add_argument("--skip-ui", action="store_true", help="Skip UI deployment")
    parser.add_argument("--skip-k8s", action="store_true", help="Skip K8s manifests")
    parser.add_argument("--tf-managed", action="store_true", help="Deprecated: Implicitly true now")

    args = parser.parse_args()

    # Load & Resolve Config
    config = load_config()
    config["args"] = vars(args)
    
    project_id = args.project_id
    region = args.region
    zone = args.zone

    # Zone Resolution Logic
    if not zone:
        # Try to infer from config if not in args
        zone = config.get("project", {}).get("zone")
    
    # Ensure consistency
    if "project" not in config: config["project"] = {}
    config["project"]["region"] = region
    config["project"]["zone"] = zone
    if args.cluster_name:
        if "cluster" not in config: config["cluster"] = {}
        config["cluster"]["name"] = args.cluster_name

    print(f"🌍 Region: {region} | 📍 Zone: {zone or 'Not Set'}")
    if args.cluster_name:
        print(f"🏢 Cluster: {args.cluster_name}")

    # Build Container
    image_uri = f"gcr.io/{project_id}/financial-advisor:latest"
    if not args.skip_build:
        print("\n--- 🏗️ Building Backend Image ---")
        run_command(["gcloud", "builds", "submit", "--tag", image_uri, "--project", project_id, "."])
    else:
        print(f"\n--- ⏭️ Skipping Build ({image_uri}) ---")

    # Deploy Application Stack
    if not args.skip_k8s:
        deploy_application_stack(
            project_id=project_id,
            region=region,
            image_uri=image_uri,
            redis_host=args.redis_host,
            redis_port=args.redis_port,
            config=config,
            skip_ui=args.skip_ui,
            cluster_name=args.cluster_name
        )
    else:
        print("⏭️ Skipping K8s Deployment")

if __name__ == "__main__":
    main()
