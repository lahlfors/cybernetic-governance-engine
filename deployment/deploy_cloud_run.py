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
Handles secret creation, image building, and service deployment.
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
    args = parser.parse_args()

    project_id = args.project_id
    region = args.region

    # 1. Secret Management
    print("\n--- 🔑 Managing Secrets ---")

    # Random Auth Token
    token = secrets.token_urlsafe(32)
    create_secret(project_id, "opa-auth-token", literal_value=token)

    # System Authz Policy
    create_secret(project_id, "system-authz-policy", file_path="deployment/system_authz.rego")

    # Finance Policy
    if os.path.exists("deployment/finance_policy.rego"):
        policy_path = "deployment/finance_policy.rego"
    else:
        # Create a dummy policy if it doesn't exist
        policy_path = "deployment/finance_policy.rego"
        with open(policy_path, "w") as f:
            f.write("package finance\nallow := true")

    create_secret(project_id, "finance-policy-rego", file_path=policy_path)

    # OPA Config
    create_secret(project_id, "opa-configuration", file_path="deployment/opa_config.yaml")

    # 2. Build Image
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

    # 3. Prepare Service YAML
    print("\n--- 📝 Preparing Service Configuration ---")

    with open("deployment/service.yaml", "r") as f:
        service_config = yaml.safe_load(f)

    # Update Ingress Image
    containers = service_config["spec"]["template"]["spec"]["containers"]
    for container in containers:
        if container["name"] == "ingress-agent":
            container["image"] = image_uri
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
        # 4. Deploy
        print("\n--- 🚀 Deploying to Cloud Run ---")
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
