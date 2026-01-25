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

def deploy_k8s_infra(project_id, region):
    """
    Deploys Kubernetes manifests for vLLM.
    Requires 'kubectl' to be configured for the target cluster.
    """
    print("\n--- ☸️ Deploying K8s Infrastructure (vLLM) ---")

    if not check_tool_availability("kubectl"):
        print("⚠️ 'kubectl' not found in PATH. Skipping K8s deployment.")
        print("   Ensure you have installed kubectl and configured context.")
        return

    k8s_dir = Path("deployment/k8s")
    if not k8s_dir.exists():
        print(f"⚠️ K8s directory {k8s_dir} not found. Skipping.")
        return

    # Check for authentication (rudimentary check)
    try:
        run_command(["kubectl", "cluster-info"], check=True, capture_output=True)
    except Exception:
        print("⚠️ Failed to connect to Kubernetes cluster. Skipping manifest application.")
        print("   Run: gcloud container clusters get-credentials CLUSTER_NAME --region REGION")
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

            print(f"✅ Injected Envs: REDIS_HOST={redis_host}, VLLM_BASE_URL={vllm_url}")
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
