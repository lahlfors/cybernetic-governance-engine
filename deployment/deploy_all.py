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
Cloud Run Deployment Script for Governed Financial Advisor
Handles secret creation, image building, service deployment, and infrastructure verification.
"""

import yaml
import argparse
import os
import secrets
import subprocess
import sys
import tempfile

def run_command(command, check=True, capture_output=False):
    """Runs a shell command and prints the output."""
    print(f"🚀 Running: {' '.join(command)}")
    try:
        result = subprocess.run(
            command,
            check=check,
            capture_output=capture_output,
            text=True
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

def enable_apis(project_id):
    """Enables necessary Google Cloud APIs."""
    print("\n--- 🛠️ Enabling APIs ---")
    apis = [
        "redis.googleapis.com",
        "aiplatform.googleapis.com",
        "secretmanager.googleapis.com",
        "run.googleapis.com",
        "cloudbuild.googleapis.com"
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

def ensure_agent_engine(project_id, location, agent_engine_id=None, force_deploy=False, staging_bucket=None):
    """
    Deploys an Agent Engine (ReasoningEngine) for Memory Bank usage.
    If agent_engine_id is provided, uses that instead of deploying.
    Returns the Agent Engine ID to use.
    
    CLI Pattern Reference:
    - Deploy: adk deploy agent_engine --project=PROJECT --region=REGION --env_file=.env
    """
    print(f"\n--- 🧠 Deploying Vertex AI Agent Engine ({location}) ---")

    # If existing ID provided, use it directly (no deployment needed)
    if agent_engine_id:
        print(f"ℹ️ Using provided Agent Engine ID: {agent_engine_id}")
        return agent_engine_id

    # Deploy new Agent Engine using ADK CLI
    return _deploy_agent_engine(project_id, location, staging_bucket)


def _deploy_agent_engine(project_id, location, staging_bucket=None):
    """
    Deploys a new Agent Engine (ReasoningEngine) using the ADK CLI.
    Returns the new engine ID on success, None on failure.
    """
    print("🚀 Deploying to Vertex AI Agent Engine using ADK CLI...")
    print("⏳ This operation may take several minutes...")

    # Load environment variables to find bucket if not provided
    from dotenv import load_dotenv
    load_dotenv()
    
    if not staging_bucket:
        # Check for GOOGLE_CLOUD_STORAGE_BUCKET in .env
        staging_bucket = os.environ.get("GOOGLE_CLOUD_STORAGE_BUCKET")
        if staging_bucket:
            print(f"ℹ️  Using staging bucket from .env: {staging_bucket}")
        else:
            print("⚠️  Warning: GOOGLE_CLOUD_STORAGE_BUCKET not found in .env. ADK may fail if no bucket config exists.")

    # The adk deploy agent_engine command deploys to Vertex AI Agent Engine
    # Use --env_file to pull config from .env
    # AGENT is the positional arg (path to agent source code folder)
    deploy_cmd = [
        "adk", "deploy", "agent_engine",
        f"--project={project_id}",
        f"--region={location}",
        "--env_file=.env",
        "--display_name=financial-advisor-agent",
        "--trace_to_cloud",
        "src"  # Positional AGENT argument - path to agent source
    ]
    
    # Add explicit staging bucket if successfully resolved
    if staging_bucket:
        deploy_cmd.insert(-1, f"--staging_bucket={staging_bucket}")
    
    result = run_command(deploy_cmd, check=False, capture_output=True)
    
    if result.returncode == 0:
        print("✅ Agent Engine deployment completed successfully!")
        
        # 1. Try to extract the engine ID from the ADK output
        if result.stdout:
            import re
            match = re.search(r'reasoningEngines/([0-9]+)', result.stdout)
            if match:
                engine_id = match.group(1)
                print(f"✅ Deployed Agent Engine ID: {engine_id}")
                return engine_id

        # 2. Reliable Retrieval: List the most recently created engine
        print("🔍 Retrieving deployed engine ID from Vertex AI...")
        # Uses gcloud beta ai reasoning-engines list sorted by creation time
        # Format: projects/.../locations/.../reasoningEngines/<ID>
        search_cmd = [
            "gcloud", "beta", "ai", "reasoning-engines", "list",
            f"--region={location}",
            f"--project={project_id}",
            "--filter=display_name=financial-advisor-agent", 
            "--sort-by=~createTime",
            "--limit=1",
            "--format=value(name)" 
        ]
        
        # Note: This requires gcloud beta component.
        search_result = run_command(search_cmd, check=False, capture_output=True)
        
        if search_result.returncode == 0 and "reasoningEngines/" in search_result.stdout:
            # Output is full resource name
            engine_id = search_result.stdout.strip().split("reasoningEngines/")[-1]
            print(f"✅ Deployed Agent Engine: {engine_id}")
            return engine_id
        
        print("⚠️ Could not retrieve engine ID automatically.")
        print("   To find your engine manually:")
        print(f"   gcloud beta ai reasoning-engines list --region={location} --project={project_id}")
        return None
    else:
        print(f"❌ Agent Engine deployment failed.")
        if result.stderr:
            print(f"   Error: {result.stderr}")
        if result.stdout:
            print(f"   Output: {result.stdout}")
        print("\n   Manual deployment options:")
        print(f"   1. Run: adk deploy agent_engine --project={project_id} --region={location} --staging_bucket={staging_bucket} financial_advisor")
        print("   2. Deploy via Vertex AI Agent Builder Console")
        print("   3. Pass existing engine ID: --agent-engine-id YOUR_ENGINE_ID")
        return None


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
        # Check if service exists and return its URL
        existing_url = check_service_exists(project_id, region, ui_service_name)
        if existing_url:
            print(f"   Existing UI service at: {existing_url}")
            return existing_url
        return None

    # Check if ui/ directory exists
    ui_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui")
    if not os.path.exists(ui_dir):
        print(f"❌ UI directory not found at: {ui_dir}")
        print("   Skipping UI deployment.")
        return None

    # Build UI image
    ui_image_uri = f"gcr.io/{project_id}/financial-advisor-ui:latest"
    print(f"\n🏗️ Building UI container image...")
    run_command([
        "gcloud", "builds", "submit",
        "--tag", ui_image_uri,
        "--project", project_id,
        ui_dir
    ])

    # Deploy UI service
    print(f"\n🚀 Deploying UI service to Cloud Run...")
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

    # Get the deployed URL
    deployed_url = check_service_exists(project_id, region, ui_service_name)
    if deployed_url:
        print(f"✅ UI service deployed at: {deployed_url}")
        return deployed_url

    print("⚠️ UI deployment completed but could not retrieve URL.")
    return None

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

def main():
    parser = argparse.ArgumentParser(
        description="Deploy Financial Advisor to Cloud Run (deploys all services by default)"
    )
    parser.add_argument("--project-id", required=True, help="Google Cloud Project ID")
    parser.add_argument("--region", default="us-central1", help="Cloud Run Region")
    parser.add_argument("--service-name", default="governed-financial-advisor", help="Cloud Run Service Name")

    # Build/Deploy Skip Flags
    parser.add_argument("--skip-build", action="store_true", help="Skip image build step")
    parser.add_argument("--skip-agent-deploy", action="store_true", help="Skip Agent Engine deployment (use existing)")
    parser.add_argument("--skip-redis", action="store_true", help="Skip Redis provisioning")
    parser.add_argument("--skip-ui", action="store_true", help="Skip UI service deployment")

    # Override Arguments (use existing resources)
    parser.add_argument("--agent-engine-id", help="Use existing Agent Engine ID (skips auto-deploy)")
    parser.add_argument("--redis-host", help="Use existing Redis Host")
    parser.add_argument("--redis-port", default="6379", help="Redis Port")
    parser.add_argument("--redis-instance-name", default="financial-advisor-redis", help="Name for auto-provisioned Redis")
    parser.add_argument("--ui-service-name", default="financial-advisor-ui", help="Cloud Run UI Service Name")
    parser.add_argument("--staging-bucket", help="GCS bucket for Agent Engine staging (default: from .env)")

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

    # 2. Infrastructure Provisioning - Agent Engine
    if args.skip_agent_deploy:
        print("\n--- ⏭️ Skipping Agent Engine deployment (--skip-agent-deploy flag set) ---")
        agent_engine_id = args.agent_engine_id  # May be None
        if not agent_engine_id:
            print("⚠️ Warning: No Agent Engine ID provided. Memory will be ephemeral.")
    else:
        # Deploy by default (force_deploy=True unless existing ID provided)
        force_deploy = not bool(args.agent_engine_id)  # Force if no ID provided
        agent_engine_id = ensure_agent_engine(project_id, region, args.agent_engine_id, force_deploy, args.staging_bucket)

    # 2. Secret Management
    print("\n--- 🔑 Managing Secrets ---")

    # Random Auth Token
    token = secrets.token_urlsafe(32)
    create_secret(project_id, "opa-auth-token", literal_value=token)

    # System Authz Policy
    create_secret(project_id, "system-authz-policy", file_path="deployment/system_authz.rego")

    # Finance Policy
    if os.path.exists("governance_poc/finance_policy.rego"):
        policy_path = "governance_poc/finance_policy.rego"
    elif os.path.exists("deployment/finance_policy.rego"):
        policy_path = "deployment/finance_policy.rego"
    else:
        print("⚠️ Warning: finance_policy.rego not found. Creating dummy.")
        policy_path = "deployment/finance_policy.rego"
        with open(policy_path, "w") as f:
            f.write("package finance\nallow := true")

    print(f"📄 Using Finance Policy from: {policy_path}")
    create_secret(project_id, "finance-policy-rego", file_path=policy_path)

    # OPA Config
    create_secret(project_id, "opa-configuration", file_path="deployment/opa_config.yaml")

    # 3. Build Image
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

    # 4. Prepare Service YAML
    print("\n--- 📝 Preparing Service Configuration ---")

    with open("deployment/service.yaml", "r") as f:
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

            if agent_engine_id:
                add_env("AGENT_ENGINE_ID", agent_engine_id)

            add_env("REDIS_HOST", redis_host)
            add_env("REDIS_PORT", redis_port)
            add_env("GOOGLE_CLOUD_PROJECT", project_id)
            add_env("GOOGLE_CLOUD_LOCATION", region)

            print(f"✅ Injected Envs: REDIS_HOST={redis_host}")
            break

    # Guarantee Secret Name Consistency
    volumes = service_config["spec"]["template"]["spec"]["volumes"]
    for volume in volumes:
        if volume["name"] == "policy-volume":
            volume["secret"]["secretName"] = "finance-policy-rego"
            print("✅ Enforced secretName: finance-policy-rego for policy-volume")
            break

    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix=".yaml", delete=False) as temp:
        yaml.dump(service_config, temp)
        temp_path = temp.name

    try:
        # 5. Deploy
        print("\n--- 🚀 Deploying to Cloud Run ---")

        # Note: Cloud Run needs VPC connector to access Redis (Memorystore).
        # This script assumes a VPC Connector is set up or Redis is accessible.
        # Adding VPC connector automation is highly complex (Networking).
        # We assume the default VPC or a Serverless VPC Access connector is configured if required.

        print("⚠️  IMPORTANT: ensuring connectivity to Redis...")
        print("   Cloud Run requires a 'Serverless VPC Access' connector to reach Cloud Memorystore (Redis).")
        print("   If you have not configured a VPC connector, the application will timeout connecting to Redis")
        print("   and fallback to 'Ephemeral Mode' (Local State only). Safety state will NOT persist across restarts.")
        print("   To fix: Create a VPC connector and add '--vpc-connector' to the gcloud run deploy command manually.")

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

        # 6. Deploy UI Service
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
