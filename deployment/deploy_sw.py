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
Serverless Deployment Script for Governed Financial Advisor (Gemini Enterprise)

Architecture:
1. Agent Engine (Vertex AI) - Core Logic (Backend for Gemini Agents)
2. Cloud Run (Gateway) - Interface & Tool Execution
3. Cloud Run (OPA) - Policy Engine

Prerequisites:
- Google Cloud Project with Billing Enabled
- APIs: aiplatform.googleapis.com, run.googleapis.com, cloudbuild.googleapis.com, discoveryengine.googleapis.com
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time

from pathlib import Path

# Ensure project root is in sys.path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from deployment.lib.utils import load_dotenv, run_command
from deployment.lib.config import load_config

# Import Registration Logic (Dynamic import to avoid hard failure if dep missing during bootstrap)
try:
    from register_agent import register_agent, list_engines, create_engine
    HAS_DISCOVERY_ENGINE = True
except ImportError:
    HAS_DISCOVERY_ENGINE = False
    print("⚠️ 'google-cloud-discoveryengine' not found. Agent registration will be skipped.")

load_dotenv()

# --- Helpers ---

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

def create_opa_dockerfile(build_dir):
    """Creates a temporary Dockerfile for OPA."""
    dockerfile_content = """
FROM openpolicyagent/opa:latest-static
# Copy policy
COPY finance_policy.rego /policy/finance_policy.rego
# Run OPA server on port 8080 (Cloud Run default)
CMD ["run", "--server", "--addr", ":8080", "/policy/finance_policy.rego"]
"""
    with open(build_dir / "Dockerfile", "w") as f:
        f.write(dockerfile_content)

# --- Service Deployments ---

def deploy_opa_service(project_id, region):
    """Deploys OPA as a standalone Cloud Run service."""
    service_name = "opa-service"
    print(f"\n--- 🛡️ Deploying OPA Service: {service_name} ---")

    # Prepare Build Context
    with tempfile.TemporaryDirectory() as tmpdir:
        build_dir = Path(tmpdir)
        
        # Copy Policy
        policy_src = Path("src/governed_financial_advisor/governance/policy/finance_policy.rego")
        if not policy_src.exists():
            # Fallback for demo/test
            policy_src = Path("deployment/finance_policy.rego")
        
        if not policy_src.exists():
             print("❌ OPA Policy file not found. Skipping OPA deployment.")
             return None

        shutil.copy(policy_src, build_dir / "finance_policy.rego")
        create_opa_dockerfile(build_dir)
        
        image_uri = f"gcr.io/{project_id}/opa-service:latest"
        print("   Building OPA image...")
        run_command([
            "gcloud", "builds", "submit",
            "--tag", image_uri,
            "--project", project_id,
            str(build_dir)
        ])

        # Deploy
        run_command([
            "gcloud", "run", "deploy", service_name,
            "--image", image_uri,
            "--region", region,
            "--project", project_id,
            "--platform", "managed",
            "--allow-unauthenticated", # Internal service
            "--port", "8080",
            "--memory", "256Mi",
            "--cpu", "1"
        ])

    url = check_service_exists(project_id, region, service_name)
    print(f"✅ OPA Service deployed at: {url}")
    return url

def deploy_gateway_service(project_id, region, opa_url):
    """Deploys Gateway as a Cloud Run service."""
    service_name = "gateway-service"
    image_uri = f"gcr.io/{project_id}/financial-advisor:latest"
    print(f"\n--- ⛩️ Deploying Gateway Service: {service_name} ---")

    env_vars = [
        f"OPA_URL={opa_url}/v1/data/finance/decision",
        f"MODEL_FAST={os.environ.get('MODEL_FAST', 'gemini-2.5-flash-lite')}",
        f"MODEL_REASONING={os.environ.get('MODEL_REASONING', 'gemini-2.5-pro')}",
        f"LANGFUSE_HOST={os.environ.get('LANGFUSE_HOST', 'https://us.cloud.langfuse.com')}",
        f"LANGFUSE_PUBLIC_KEY={os.environ.get('LANGFUSE_PUBLIC_KEY', '')}",
        f"LANGFUSE_SECRET_KEY={os.environ.get('LANGFUSE_SECRET_KEY', '')}",
        f"GOOGLE_CLOUD_PROJECT={project_id}",
        f"GOOGLE_CLOUD_LOCATION={region}"
    ]

    run_command([
        "gcloud", "run", "deploy", service_name,
        "--image", image_uri,
        "--region", region,
        "--project", project_id,
        "--service-account", f"gateway-sa@{project_id}.iam.gserviceaccount.com",
        "--set-env-vars", ",".join(env_vars),
        "--command", "uvicorn,src.gateway.server.main:app,--host,0.0.0.0,--port,8080",
        "--allow-unauthenticated", # Gateway is the entry point
        "--port", "8080",
        "--memory", "1Gi",
        "--cpu", "1"
    ])

    url = check_service_exists(project_id, region, service_name)
    print(f"✅ Gateway deployed at: {url}")
    return url

def deploy_agent_engine(project_id, region, staging_bucket, gateway_url):
    """Deploys Vertex AI Reasoning Engine (Backend for Gemini Agents)."""
    print(f"\n--- 🧠 Deploying Agent Engine (Gemini Enterprise Backend) ---")
    try:
        import vertexai
        from vertexai.preview import reasoning_engines
        from src.governed_financial_advisor.reasoning_engine import FinancialAdvisorEngine
    except ImportError:
        print("❌ Failed to import vertexai SDK.")
        return None

    vertexai.init(project=project_id, location=region, staging_bucket=f"gs://{staging_bucket}")

    requirements = [
        "google-cloud-aiplatform[agent-engines]",
        "langchain-google-vertexai",
        "langchain-google-genai",
        "langgraph",
        "pydantic",
        "google-auth",
        "yfinance",
        "pandas",
        "httpx",
        "nest_asyncio"
    ]

    print("   Creating Reasoning Engine...")
    try:
        remote_agent = reasoning_engines.ReasoningEngine.create(
            FinancialAdvisorEngine(project=project_id, location=region, gateway_url=gateway_url),
            requirements=requirements,
            extra_packages=["src", "config"],
            display_name="financial-advisor-engine",
            description="Governed Financial Advisor (Gemini Enterprise Ready)",
        )
        print(f"✅ Agent Engine Deployed: {remote_agent.resource_name}")
        return remote_agent
    except Exception as e:
        print(f"❌ Failed to deploy Agent Engine: {e}")
        return None

def perform_gemini_registration(project_id, region, reasoning_engine_resource_name):
    """Registers the deployed Reasoning Engine with Gemini Enterprise (Agent Builder)."""
    if not HAS_DISCOVERY_ENGINE:
        print("⏭️ Skipping Gemini Registration (dependency missing).")
        return

    print(f"\n--- 💎 Registering with Gemini Enterprise ---")

    # Discovery Engine/Agent Builder location might differ (often 'global' or 'us-central1')
    # For Agents, usually match the reasoning engine location if supported, or use 'global'.
    # Defaulting to 'global' for Agent Builder is common, but let's try the region first or default to 'global' if fails?
    # Actually, usually Agent Builder apps are location-specific (us, eu, or global).
    # Let's use the provided region.

    app_id = "financial-advisor-app"

    try:
        # 1. Ensure App/Engine exists
        engines = list_engines(project_id, region)
        found_engine = next((e for e in engines if e.name.endswith(f"/engines/{app_id}")), None)

        if not found_engine:
            print(f"   Creating new Agent App '{app_id}'...")
            try:
                found_engine = create_engine(project_id, region, "Financial Advisor", app_id)
            except Exception as e:
                 print(f"   ⚠️ Could not create Engine (might need to use 'global' location?): {e}")
                 # Fallback logic could go here, but keep simple for now
                 return
        else:
             print(f"   Found existing Agent App: {found_engine.name}")

        # 2. Register Agent
        register_agent(project_id, region, app_id, reasoning_engine_resource_name, "Financial Advisor")

    except Exception as e:
        print(f"❌ Gemini Registration Failed: {e}")
        print("   Please register manually in the Agent Console.")

# --- Main ---

def main():
    parser = argparse.ArgumentParser(description="Deploy Financial Advisor App (Gemini Enterprise)")
    parser.add_argument("--project-id", default=os.environ.get("GOOGLE_CLOUD_PROJECT"), help="GCP Project ID")
    parser.add_argument("--region", default=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"), help="GCP Region")
    parser.add_argument("--skip-build", action="store_true", help="Skip Backend Build")
    parser.add_argument("--skip-registration", action="store_true", help="Skip Gemini App Registration")

    args = parser.parse_args()
    project_id = args.project_id
    region = args.region

    if not project_id:
        print("❌ Project ID required.")
        sys.exit(1)

    print(f"🚀 Deploying to Project: {project_id} in {region}")

    # 1. Build Backend Image
    image_uri = f"gcr.io/{project_id}/financial-advisor:latest"
    if not args.skip_build:
        print("\n--- 🏗️ Building Backend Image ---")
        run_command(["gcloud", "builds", "submit", "--tag", image_uri, "--project", project_id, "."])

    # 2. Deploy OPA
    opa_url = deploy_opa_service(project_id, region)
    if not opa_url:
        print("⚠️ OPA deployment failed or skipped. Gateway might fail.")
        opa_url = "http://localhost:8181"

    # 3. Deploy Gateway
    gateway_url = deploy_gateway_service(project_id, region, opa_url)

    # 4. Deploy Agent Engine
    staging_bucket = f"{project_id}-agent-artifacts"
    run_command(["gcloud", "storage", "buckets", "create", f"gs://{staging_bucket}", "--project", project_id, "--location", region], check=False)

    remote_agent = deploy_agent_engine(project_id, region, staging_bucket, gateway_url)

    # 5. Register with Gemini Enterprise
    if remote_agent and not args.skip_registration:
        perform_gemini_registration(project_id, region, remote_agent.resource_name)

    print("\n✅ Deployment Complete!")

if __name__ == "__main__":
    main()
