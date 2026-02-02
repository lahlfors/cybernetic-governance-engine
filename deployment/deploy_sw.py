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

def deploy_ui_service(project_id, region, ui_service_name, backend_url, skip_ui=False, target_gke=True):
    """
    Deploys UI service.
    If target_gke=True, deploys to GKE.
    If target_gke=False, deploys to Cloud Run.
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

    if target_gke:
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

    else:
        # Cloud Run Deployment
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

def deploy_gateway_service(project_id, region, vllm_endpoint):
    """
    Deploys the Gateway as a Cloud Run Service.
    Assumes the container image is already built (same as backend).
    """
    service_name = "gateway-service"
    image_uri = f"gcr.io/{project_id}/financial-advisor:latest"
    print(f"\n--- ⛩️ Deploying Gateway Service: {service_name} ---")

    # Cloud Run Deployment
    # We use the same image as the backend, but we might want a specific entrypoint or env var to run just the Gateway?
    # For now, assuming the image can run as gateway if configured.
    # We need to set GATEWAY_MODE=true or similar if the entrypoint differs,
    # but currently main.py starts the server. We likely need a dedicated entrypoint or CMD override.
    # The Dockerfile runs "uv run uvicorn src.governed_financial_advisor.server:app".
    # We need to run "uv run python -m src.gateway.server.main" (gRPC server).

    cmd = [
        "gcloud", "run", "deploy", service_name,
        "--image", image_uri,
        "--region", region,
        "--project", project_id,
        "--service-account", f"gateway-sa@{project_id}.iam.gserviceaccount.com",
        "--set-env-vars", f"VLLM_ENDPOINT={vllm_endpoint},StartMode=GATEWAY",
        "--command", "python,-m,src.gateway.server.main",
        # "--allow-unauthenticated", # Protected by IAM Invoker
        "--no-allow-unauthenticated",
        "--vpc-egress", "all-traffic", # Required to reach GKE private IP
        "--use-http2", # Required for gRPC
        "--port", "8080" # Explicitly tell Cloud Run to listen on 8080 (app respects $PORT)
    ]

    # Check if network/subnet is specified in config? Terraform sets it.
    # If we use `gcloud run deploy`, it might overwrite Terraform settings if we are not careful.
    # However, since we use the same service name, it acts as a revision update.
    # We should respect the infrastructure set by Terraform.

    run_command(cmd)

    # Get URL
    url = check_service_exists(project_id, region, service_name)
    print(f"✅ Gateway deployed at: {url}")
    return url

def deploy_reasoning_engine(project_id, region, staging_bucket, redis_host):
    """
    Deploys the Agent as a Vertex AI Reasoning Engine.
    """
    print(f"\n--- 🧠 Deploying Vertex AI Reasoning Engine ---")

    try:
        import vertexai
        from vertexai.preview import reasoning_engines
        from src.governed_financial_advisor.reasoning_engine import FinancialAdvisorEngine
    except ImportError:
        print("❌ Failed to import vertexai SDK. Please install google-cloud-aiplatform[agent-engines].")
        return None

    vertexai.init(project=project_id, location=region, staging_bucket=f"gs://{staging_bucket}")

    # Define requirements for the remote environment
    requirements = [
        "google-cloud-aiplatform[agent-engines]",
        "langchain-google-vertexai",
        "langchain-google-genai",
        "langgraph",
        "langgraph-checkpoint-redis",
        "redis",
        "pydantic",
        "google-auth",
        "nemoguardrails",
        "yfinance",
        "pandas",
        "httpx"
    ]

    print("   Creating Reasoning Engine (this may take a few minutes)...")
    try:
        # Remote creation
        redis_url = f"redis://{redis_host}:6379" if redis_host else None
        
        remote_agent = reasoning_engines.ReasoningEngine.create(
            FinancialAdvisorEngine(project=project_id, location=region, redis_url=redis_url),
            requirements=requirements,
            extra_packages=["src"],
            display_name="financial-advisor-engine",
            description="Governed Financial Advisor (Hybrid Architecture)",
        )
        print(f"✅ Reasoning Engine Deployed: {remote_agent.resource_name}")
        return remote_agent
    except Exception as e:
        print(f"❌ Failed to deploy Reasoning Engine: {e}")
        return None


# --- Application Deployment Logic ---

def deploy_application_stack(project_id, region, image_uri, redis_host, redis_port, config, cluster_name=None):
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

    # 5. Deploy Backend
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
    manifest_content = manifest_content.replace("${MODEL_FAST}", os.environ.get("MODEL_FAST", "gemini-2.5-flash-lite"))
    manifest_content = manifest_content.replace("${MODEL_REASONING}", os.environ.get("MODEL_REASONING", "gemini-2.5-pro"))
    manifest_content = manifest_content.replace("${DEPLOY_TIMESTAMP}", timestamp)
    manifest_content = manifest_content.replace("${OTEL_EXPORTER_OTLP_ENDPOINT}", os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", ""))
    manifest_content = manifest_content.replace("${OTEL_EXPORTER_OTLP_HEADERS}", os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", ""))

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
    if True: # Always attempt if not skipped (logic inside function)
        # For GKE, backend_url might not be needed if using internal DNS, but passing it anyway
        deploy_ui_service(project_id, region, "financial-advisor-ui", backend_url, skip_ui=skip_ui, target_gke=True)

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

    parser.add_argument("--skip-k8s", action="store_true", help="Skip K8s manifests")
    parser.add_argument("--deploy-agent-engine", action="store_true", help="Deploy using Vertex AI Agent Engine (Hybrid Mode)")
    parser.add_argument("--agent-engine-name", help="Existing Agent Engine Resource Name (skips creation)")
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
    if args.deploy_agent_engine:
        # Hybrid Mode: GKE (vLLM) + Cloud Run (Gateway) + Agent Engine (Reasoning)

        # 1. Base GKE (vLLM only)
        deploy_k8s_infra(project_id, config)

        # 2. Deploy Gateway (Cloud Run)
        vllm_ip = run_command(
             ["kubectl", "get", "service", "vllm-inference", "-n", "governance-stack", "-o", "jsonpath='{.spec.clusterIP}'"],
             check=False, capture_output=True
        ).stdout.strip().strip("'")
        vllm_endpoint = f"http://{vllm_ip}:8000" if vllm_ip else "http://vllm-inference.governance-stack.svc.cluster.local:8000"

        deploy_gateway_service(project_id, region, vllm_endpoint)

        # 3. Deploy Reasoning Engine
        if args.agent_engine_name:
             print(f"ℹ️ Skipping Reasoning Engine creation (provided): {args.agent_engine_name}")
             # We might want to fetch the object to get the URL or similar if needed, but resource_name is usually enough for UI?
             # The UI currently expects a URL.
             # Reasoning Engine has no "URL" in the same way as Cloud Run. It's an API resource.
             # We might need to construct the URL or just pass the resource name.
             # For now, we'll assume the UI or Gateway handles it.
        else:
            staging_bucket = f"{project_id}-agent-artifacts"
            deploy_reasoning_engine(project_id, region, staging_bucket, None)



    elif not args.skip_k8s:
        # Standard GKE Deployment
        deploy_application_stack(
            project_id=project_id,
            region=region,
            image_uri=image_uri,
            redis_host=args.redis_host,
            redis_port=args.redis_port,
            config=config,

            cluster_name=args.cluster_name
        )
    else:
        print("⏭️ Skipping K8s Deployment")

if __name__ == "__main__":
    main()
