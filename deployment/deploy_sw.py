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
GKE Deployment Script for Governed Financial Advisor

Handles:
1. Google Cloud API enablement.
2. Secret Manager configuration (tokens, OPA policies).
3. Kubernetes Infrastructure (vLLM on GKE).
4. Gateway & Backend Service Deployment (GKE).
5. UI Service Deployment (GKE).

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

def build_gateway_image(project_id):
    """Builds the Gateway container image."""
    gateway_image_uri = f"gcr.io/{project_id}/gateway:latest"
    print(f"\n--- 🏗️ Building Gateway Image: {gateway_image_uri} ---")
    
    # Check if src/gateway exists
    if not Path("src/gateway").exists():
        print("❌ src/gateway directory not found. Skipping Gateway build.")
        return None

    # Create a temporary Cloud Build config
    cloudbuild_yaml = f"""
steps:
- name: 'gcr.io/cloud-builders/docker'
  args: ['build', '-t', '{gateway_image_uri}', '-f', 'src/gateway/Dockerfile', '.']
images:
- '{gateway_image_uri}'
"""
    cb_file = Path("gateway_cloudbuild.yaml")
    with open(cb_file, "w") as f:
        f.write(cloudbuild_yaml)

    try:
        run_command([
            "gcloud", "builds", "submit",
            "--config", str(cb_file),
            "--project", project_id,
            "." # Build context is root
        ])
    finally:
        if cb_file.exists():
            cb_file.unlink() # Cleanup

    return gateway_image_uri

def deploy_ui_service(project_id, region, ui_service_name, backend_url, skip_ui=False):
    """
    Deploys UI service to GKE.
    """
    print(f"\n--- 🖥️ Deploying UI Service: {ui_service_name} ---")

    if skip_ui:
        print("⏭️ Skipping UI deployment (--skip-ui flag set)")
        # For now, just return None if skipped, or try getting existing URL if we really wanted to check
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

    print(f"\n--- ☸️ Deploying UI to GKE ---")
    deployment_tpl = Path("deployment/k8s/frontend-deployment.yaml.tpl")
    if not deployment_tpl.exists():
        print(f"❌ Frontend manifest template not found at {deployment_tpl}")
        return None

    with open(deployment_tpl) as f:
        manifest_content = f.read()

    manifest_content = manifest_content.replace("${UI_IMAGE_URI}", ui_image_uri)
    # BACKEND_URL in K8s is internal service DNS usually, but here we can rely on template default
    # or override if we passed an external URL (though for GKE-to-GKE, internal DNS is better)
    # The template defaults to http://governed-financial-advisor.governance-stack.svc.cluster.local:80
    # If we wanted to support both, we'd substitute BACKEND_URL too.
    # Let's assume the template has the correct internal DNS for now or we substitute it if variable exists.

    # Write Generated Manifest
    generated_dir = Path("deployment/k8s/generated")
    generated_dir.mkdir(parents=True, exist_ok=True)
    generated_file = generated_dir / "frontend-deployment.yaml"

    with open(generated_file, 'w') as f:
        f.write(manifest_content)

    print(f"📄 Generated manifest: {generated_file}")
    run_command(["kubectl", "apply", "-f", str(generated_file)])
    print("✅ UI manifest applied.")

    # Wait for LoadBalancer IP
    print("\n--- ⏳ Waiting for UI IP ---")
    for _ in range(30):
        result = run_command(
            ["kubectl", "get", "service", "financial-advisor-ui", "-n", "governance-stack", "-o", "jsonpath='{.status.loadBalancer.ingress[0].ip}'"],
            check=False, capture_output=True
        )
        ip = result.stdout.strip("'")
        if ip:
            url = f"http://{ip}"
            print(f"✅ Found UI IP: {ip}")
            return url
        print("   Waiting for LoadBalancer IP...")
        time.sleep(10)
    return None


# --- Application Deployment Logic ---

def deploy_application_stack(project_id, region, image_uri, redis_host, redis_port, config, skip_ui=False, cluster_name=None):
    """
    Orchestrates Application Deployment on top of provisions Infrastructure:
    1. Deploys/Updates vLLM Inference Engine (GKE).
    2. Mirrors Secrets from Secret Manager/Env to K8s.
    3. Deploys Backend Service (GKE).
    4. Deploys UI Service (GKE).
    """
    accelerator = config.get("args", {}).get("accelerator", "gpu")
    print(f"\n--- 🚀 Starting Application Deployment [Accelerator: accelerator] ---")

    # Clean previous generated manifests to avoid applying stale/invalid configs
    generated_dir = Path("deployment/k8s/generated")
    if generated_dir.exists():
        print(f"🧹 Cleaning generated manifests in {generated_dir}")
        for item in generated_dir.iterdir():
            if item.is_file():
                item.unlink()

    # 1. Deploy vLLM / K8s Base Infra
    # This ensures the cluster is configured and vLLM is running
    deploy_k8s_infra(project_id, config)

    # 2. Redis Configuration
    if not redis_host:
        print("ℹ️ No Redis Host provided. Defaulting to internal Redis on GKE.")
        redis_host = "redis.governance-stack.svc.cluster.local"


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

    # 4. Apply Service Account for Workload Identity
    sa_manifest = Path("deployment/k8s/service-account.yaml")
    if sa_manifest.exists():
        print("\n--- 🔑 Applying Kubernetes Service Account ---")
        with open(sa_manifest) as f:
            sa_content = f.read()
        sa_content = sa_content.replace("${PROJECT_ID}", project_id)

        # Write resolved manifest
        generated_dir = Path("deployment/k8s/generated")
        generated_dir.mkdir(parents=True, exist_ok=True)
        sa_generated = generated_dir / "service-account.yaml"
        with open(sa_generated, 'w') as f:
            f.write(sa_content)
        run_command(["kubectl", "apply", "-f", str(sa_generated)])

    # 5. Define Substitutions (Moved up for Gateway)
    timestamp = str(int(time.time()))
    substitutions = {
        # Infrastructure
        "${IMAGE_URI}": image_uri,
        "${REDIS_HOST}": redis_host,
        "${REDIS_PORT}": redis_port,
        "${GOOGLE_CLOUD_PROJECT}": project_id,
        "${GOOGLE_CLOUD_LOCATION}": region,
        "${DEPLOY_TIMESTAMP}": timestamp,
        "${PORT}": os.environ.get("PORT", "8080"),
        
        # Model Configuration (Tiered)
        "${MODEL_FAST}": os.environ.get("MODEL_FAST", ""),
        "${MODEL_REASONING}": os.environ.get("MODEL_REASONING", ""),
        "${MODEL_CONSENSUS}": os.environ.get("MODEL_CONSENSUS", os.environ.get("MODEL_REASONING", "")),
        
        # vLLM Endpoints
        "${VLLM_BASE_URL}": os.environ.get("VLLM_BASE_URL", "http://vllm-service.governance-stack.svc.cluster.local:8000/v1"),
        "${VLLM_API_KEY}": os.environ.get("VLLM_API_KEY", "EMPTY"),
        # Fix: Use the value of VLLM_BASE_URL from above if env var is not set, not os.environ.get which returns empty
        "${VLLM_FAST_API_BASE}": os.environ.get("VLLM_FAST_API_BASE", os.environ.get("VLLM_BASE_URL", "http://vllm-service.governance-stack.svc.cluster.local:8000/v1")),
        "${VLLM_REASONING_API_BASE}": os.environ.get("VLLM_REASONING_API_BASE", os.environ.get("VLLM_BASE_URL", "http://vllm-service.governance-stack.svc.cluster.local:8000/v1")),
        
        # Policy Engine
        "${OPA_URL}": os.environ.get("OPA_URL", "http://localhost:8181/v1/data/finance/allow"),

        # Inference Gateway
        "${VLLM_GATEWAY_URL}": os.environ.get("VLLM_GATEWAY_URL", ""),
        
        # Langfuse (Hot Tier)
        "${LANGFUSE_PUBLIC_KEY}": os.environ.get("LANGFUSE_PUBLIC_KEY", ""),
        "${LANGFUSE_SECRET_KEY}": os.environ.get("LANGFUSE_SECRET_KEY", ""),
        "${LANGFUSE_HOST}": os.environ.get("LANGFUSE_HOST", ""),
        
        # OpenTelemetry (Cold Tier)
        "${OTEL_EXPORTER_OTLP_ENDPOINT}": os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", ""),
        "${OTEL_EXPORTER_OTLP_HEADERS}": os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", ""),
        "${TRACE_SAMPLING_RATE}": os.environ.get("TRACE_SAMPLING_RATE", "0.01"),
        
        # Cold Tier Storage
        "${COLD_TIER_GCS_BUCKET}": os.environ.get("COLD_TIER_GCS_BUCKET", ""),
        "${COLD_TIER_GCS_PREFIX}": os.environ.get("COLD_TIER_GCS_PREFIX", "cold_tier"),
        
        # MCP Configuration
        "${MCP_MODE}": os.environ.get("MCP_MODE", "stdio"),
        "${ALPHAVANTAGE_API_KEY}": os.environ.get("ALPHAVANTAGE_API_KEY", ""),
        
        # Gateway Configuration
        "${GATEWAY_HOST}": "gateway.governance-stack.svc.cluster.local",
        "${GATEWAY_GRPC_PORT}": "50051",
    }
    
    # Helper: strip surrounding quotes from .env values (they get re-quoted in YAML)
    def strip_quotes(val):
        if isinstance(val, str) and len(val) >= 2:
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                return val[1:-1]
        return val

    # 6. Deploy Gateway (Separate Service)
    print("\n--- ⛩️ Deploying Gateway Service ---")
    gateway_tpl = Path("deployment/k8s/gateway-deployment.yaml.tpl")
    if gateway_tpl.exists():
        with open(gateway_tpl) as f:
            manifest_content = f.read()
        
        # Substitute
        gateway_image = f"gcr.io/{project_id}/gateway:latest"
        
        # Reuse substitutions from backend, but ensure GATEWAY_IMAGE_URI is there
        gw_substitutions = substitutions.copy()
        gw_substitutions["${GATEWAY_IMAGE_URI}"] = gateway_image
        
        for placeholder, value in gw_substitutions.items():
            manifest_content = manifest_content.replace(placeholder, str(strip_quotes(value)))
            
        generated_dir = Path("deployment/k8s/generated")
        generated_dir.mkdir(parents=True, exist_ok=True)
        generated_file = generated_dir / "gateway-deployment.yaml"
        with open(generated_file, 'w') as f:
            f.write(manifest_content)
            
        run_command(["kubectl", "apply", "-f", str(generated_file)])
        print("✅ Gateway manifest applied.")
    else:
        print("⚠️ Gateway template not found. Skipping.")

    # 7. Deploy Backend
    print("\n--- ☸️ Deploying Backend to GKE ---")
    deployment_tpl = Path("deployment/k8s/backend-deployment.yaml.tpl")
    if not deployment_tpl.exists():
        print(f"❌ Backend manifest template not found at {deployment_tpl}")
        sys.exit(1)

    with open(deployment_tpl) as f:
        manifest_content = f.read()
    
    # Apply all substitutions (with quote stripping)
    for placeholder, value in substitutions.items():
        manifest_content = manifest_content.replace(placeholder, str(strip_quotes(value)))

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
    # ... (rest of file)
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
        print("⚠️ Failed to retrieve Backend IP via kubectl. UI deployment might default to internal DNS.")

    # 6. Deploy UI (GKE Only)
    deploy_ui_service(project_id, region, "financial-advisor-ui", backend_url, skip_ui=skip_ui)

# --- Main Execution ---

def main():
    parser = argparse.ArgumentParser(description="Deploy Financial Advisor App (GKE Only)")

    # Env Defaults
    default_project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    default_region = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    default_zone = os.environ.get("GOOGLE_CLOUD_ZONE")

    # Core Arguments
    parser.add_argument("--project-id", default=default_project, required=not default_project, help="GCP Project ID")
    parser.add_argument("--region", default=default_region, help="GCP Region")
    parser.add_argument("--zone", default=default_zone, help="GCP Zone")

    # Infrastructure Inputs (Passed from Terraform)
    parser.add_argument("--redis-host", help="Redis Host IP (Optional, defaults to MemorySaver)")
    parser.add_argument("--redis-port", default="6379", help="Redis Port")
    parser.add_argument("--cluster-name", help="GKE Cluster Name")

    # Operational Flags
    parser.add_argument("--skip-build", action="store_true", help="Skip Docker build")
    parser.add_argument("--skip-ui", action="store_true", help="Skip UI deployment")
    parser.add_argument("--skip-gateway", action="store_true", help="Skip Gateway build")
    parser.add_argument("--skip-k8s", action="store_true", help="Skip K8s manifests")
    parser.add_argument("--tf-managed", action="store_true", help="Deprecated: Implicitly true now")

    args = parser.parse_args()

    # Load & Resolve Config
    config = load_config()
    config["args"] = vars(args)

    # Sync Model Config from Env (Single Source of Truth)
    # Validating Config Source (Env wins)
    print(f"🔍 DEBUG: Config Model before overwrite: {config.get('model', {})}")

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

    # Sync Model Config from Env (Targeting vllm-inference -> MODEL_FAST)
    model_fast = os.environ.get("MODEL_FAST")
    print(f"🔍 DEBUG: MODEL_FAST from env: '{model_fast}'")
    
    if model_fast:
        config.setdefault("model", {})["name"] = model_fast
        # Clear quantization by default for Fast model (usually small) unless specified in name
        if not any(q in model_fast for q in ["AWQ", "GPTQ", "BNB", "Int8"]):
            config["model"]["quantization"] = None
        
        # Quantization logic for Fast model (if needed in future)
        if "AWQ" in model_fast or "GPTQ" in model_fast:
             config["model"]["quantization"] = "awq" # Example default
        
        # Optimize memory for 7B model on L4 (leave room for activations/FSM)
        if "7B" in model_fast or "8B" in model_fast:
             # Since we enforce node isolation (1 GPU per model), we can use more memory.
             # 0.7 was too low for 8k context.
             config["model"]["gpu_memory_utilization"] = 0.9
             print(f"ℹ️ Optimized gpu_memory_utilization to 0.9 for {model_fast}")
    
    print(f"🔍 DEBUG: Final Config Model (Inference): {config.get('model', {})}")

    # Build Container
    image_uri = f"gcr.io/{project_id}/financial-advisor:latest"
    if not args.skip_build:
        print("\n--- 🏗️ Building Backend Image ---")
        run_command(["gcloud", "builds", "submit", "--tag", image_uri, "--project", project_id, "."])
        
        # Build Gateway Image
        if not args.skip_gateway:
            build_gateway_image(project_id)
        else:
            print("\n--- ⏭️ Skipping Gateway Build ---")
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
