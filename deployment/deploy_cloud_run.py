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

def verify_agent_engine(project_id, location, agent_engine_id):
    """
    Verifies the Agent Engine ID.
    Since programmatic creation of Vertex AI Agents is complex/requires data,
    we perform a soft verification or warn the user.
    """
    print("\n--- 🧠 Verifying Vertex AI Agent Engine ---")

    if not agent_engine_id:
        print("⚠️ No --agent-engine-id provided.")
        print("   The 'financial_coordinator' agent uses Vertex AI Memory Bank for context.")
        print("   Without a valid Agent Engine ID, memory features will be disabled (Ephemeral Mode).")
        print("   Please create an Agent in Vertex AI Agent Builder and pass its ID via --agent-engine-id.")
        return

    print(f"ℹ️ Agent Engine ID provided: {agent_engine_id}")
    # Ideally, we would run: gcloud discovery-engine apps describe ...
    # But the CLI mapping isn't always 1:1 with "Agent Engine ID" depending on the resource type (Search vs Chat).
    # We assume the user provided a valid ID if they went to the trouble of passing it.
    print("✅ Using provided Agent Engine ID for deployment.")

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
    parser = argparse.ArgumentParser(description="Deploy Financial Advisor to Cloud Run")
    parser.add_argument("--project-id", required=True, help="Google Cloud Project ID")
    parser.add_argument("--region", default="us-central1", help="Cloud Run Region")
    parser.add_argument("--service-name", default="governed-financial-advisor", help="Cloud Run Service Name")
    parser.add_argument("--skip-build", action="store_true", help="Skip image build step")

    # New Arguments for Memory and Redis
    parser.add_argument("--agent-engine-id", help="Vertex AI Agent Engine ID")
    parser.add_argument("--redis-host", help="Redis Host (Optional: will provision if missing)")
    parser.add_argument("--redis-port", default="6379", help="Redis Port")
    parser.add_argument("--redis-instance-name", default="financial-advisor-redis", help="Name for auto-provisioned Redis")

    args = parser.parse_args()

    project_id = args.project_id
    region = args.region

    # 0. Enable APIs
    enable_apis(project_id)

    # 1. Infrastructure Provisioning
    redis_host = args.redis_host
    redis_port = args.redis_port

    if not redis_host:
        redis_host, redis_port = get_redis_host(project_id, region, args.redis_instance_name)
    else:
        print(f"\n--- 🗄️ Using provided Redis: {redis_host}:{redis_port} ---")

    verify_agent_engine(project_id, region, args.agent_engine_id)

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
        print("⚠️ Warning: finance_policy.rego not found in governance_poc/ or deployment/. Creating dummy.")
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

            if args.agent_engine_id:
                add_env("AGENT_ENGINE_ID", args.agent_engine_id)

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

        run_command([
            "gcloud", "run", "services", "replace", temp_path,
            "--region", region,
            "--project", project_id
        ])

        print("\n--- ✅ Deployment Complete ---")
        print(f"Service URL: gcloud run services describe {args.service_name} --region {region} --format 'value(status.url)'")

    finally:
        os.remove(temp_path)

if __name__ == "__main__":
    main()
