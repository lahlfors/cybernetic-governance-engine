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
Deployment Script for Governed Financial Advisor (GKE Edition)

Handles:
1. Validating Prerequisites (Terraform, kubectl, gcloud)
2. Applying Terraform Infrastructure (GKE, VPC, Secrets)
3. Configuring `kubectl` context
4. Building & Pushing Containers
5. Creating K8s Secrets & ConfigMaps
6. Applying Kubernetes Manifests
7. Providing Access Instructions

Configuration is read from environment variables and CLI args.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# --- Helper Functions ---

def run_command(command, check=True, capture_output=False, env=None, cwd=None):
    """
    Runs a shell command and prints the output.
    """
    cmd_str = ' '.join(command) if isinstance(command, list) else command
    print(f"🚀 Running: {cmd_str}")
    try:
        result = subprocess.run(
            command,
            check=check,
            capture_output=capture_output,
            text=True,
            env=env or os.environ.copy(),
            cwd=cwd,
            shell=isinstance(command, str)
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

def check_tool(tool_name):
    if not shutil.which(tool_name):
        print(f"❌ Error: '{tool_name}' is not installed or not in PATH.")
        sys.exit(1)

def build_and_push(project_id, image_name, build_path, dockerfile=None):
    """Builds and pushes a container image using Cloud Build."""
    tag = f"gcr.io/{project_id}/governance-stack/{image_name}:latest"
    print(f"\n🏗️ Building {image_name} -> {tag}")
    
    cmd = [
        "gcloud", "builds", "submit",
        "--tag", tag,
        "--project", project_id,
        str(build_path)
    ]
    if dockerfile:
        cmd.extend(["--config", "cloudbuild.yaml"]) # Or use docker build logic if needed, but 'submit' auto-detects Dockerfile

    run_command(cmd)
    return tag

def create_secret_from_env(secret_name, key, env_var):
    """Creates a generic K8s secret from an environment variable."""
    value = os.environ.get(env_var)
    if not value:
        print(f"⚠️ Warning: {env_var} not found in environment. Secret {secret_name} may be empty.")
        value = "placeholder-value-please-replace"

    print(f"🔒 Creating Secret: {secret_name}")
    # Idempotent creation (delete first to update)
    run_command(f"kubectl delete secret {secret_name} --ignore-not-found", shell=True)
    run_command(f"kubectl create secret generic {secret_name} --from-literal={key}={value}", shell=True)

def create_configmap_from_file(cm_name, file_path):
    """Creates a ConfigMap from a file."""
    if not Path(file_path).exists():
        print(f"⚠️ Warning: Policy file {file_path} not found. ConfigMap {cm_name} will fail.")
        return

    print(f"📄 Creating ConfigMap: {cm_name} from {file_path}")
    run_command(f"kubectl delete configmap {cm_name} --ignore-not-found", shell=True)
    run_command(f"kubectl create configmap {cm_name} --from-file={file_path}", shell=True)

# --- Main Logic ---

def main():
    parser = argparse.ArgumentParser(description="Deploy Governed Financial Advisor to GKE")
    parser.add_argument("--project-id", required=True, help="Google Cloud Project ID")
    parser.add_argument("--region", default="us-central1", help="GCP Region")
    parser.add_argument("--zone", default="us-central1-a", help="GCP Zone")
    parser.add_argument("--skip-terraform", action="store_true", help="Skip Terraform Apply step")
    parser.add_argument("--skip-build", action="store_true", help="Skip Container Build step")
    
    args = parser.parse_args()
    
    # 1. Prerequisite Checks
    print("\n--- 🔍 Checking Prerequisites ---")
    check_tool("terraform")
    check_tool("kubectl")
    check_tool("gcloud")
    
    # 2. Terraform Apply
    tf_dir = Path("deployment/terraform")
    if not args.skip_terraform:
        print("\n--- 🏗️ Applying Infrastructure (Terraform) ---")
        
        # Init
        run_command(["terraform", "init"], cwd=tf_dir)
        
        # Apply
        tf_cmd = [
            "terraform", "apply", "-auto-approve",
            f"-var=project_id={args.project_id}",
            f"-var=region={args.region}",
            f"-var=zone={args.zone}",
            f"-var=gateway_image=gcr.io/{args.project_id}/governance-stack/gateway:latest"
        ]
        run_command(tf_cmd, cwd=tf_dir)
    else:
        print("\n--- ⏭️ Skipping Terraform Apply ---")

    # 3. Configure kubectl
    print("\n--- 🔑 Configuring kubectl ---")
    cluster_name = "governance-cluster" # Defined in gke.tf
    run_command([
        "gcloud", "container", "clusters", "get-credentials", cluster_name,
        "--zone", args.zone,
        "--project", args.project_id
    ])
    
    # 4. Build Images
    if not args.skip_build:
        print("\n--- 🐳 Building Container Images ---")
        # Build Gateway (Dockerfile is in src/gateway/Dockerfile, context is root)
        # Note: We need to build from root to include shared modules if any.
        # But per Dockerfile analysis earlier, Gateway Dockerfile is at root level or src/gateway level?
        # Checked `src/gateway/Dockerfile` -> Needs specific build context.
        # Actually repo has `Dockerfile` in root for 'app' and `src/gateway/Dockerfile` for gateway?
        # Let's check file list.
        # `Dockerfile` in root is for the main app (Financial Advisor).
        # `src/gateway/Dockerfile` exists.
        # `Dockerfile.nemo` exists.
        
        # Build Gateway
        # Note: src/gateway/Dockerfile likely expects context to be root to copy src/
        run_command([
            "gcloud", "builds", "submit",
            "--tag", f"gcr.io/{args.project_id}/governance-stack/gateway:latest",
            "--file", "src/gateway/Dockerfile",
            "--project", args.project_id,
            "."
        ])

        # Build Financial Advisor (Root Dockerfile)
        run_command([
            "gcloud", "builds", "submit",
            "--tag", f"gcr.io/{args.project_id}/governance-stack/advisor:latest",
            "--file", "Dockerfile",
            "--project", args.project_id,
            "."
        ])

        # Build NeMo (Dockerfile.nemo)
        run_command([
            "gcloud", "builds", "submit",
            "--tag", f"gcr.io/{args.project_id}/governance-stack/nemo:latest",
            "--file", "Dockerfile.nemo",
            "--project", args.project_id,
            "."
        ])
    else:
         print("\n--- ⏭️ Skipping Image Build ---")

    # 5. Create Secrets & ConfigMaps
    print("\n--- 🔐 Configuring K8s Secrets ---")
    
    # vLLM HF Token
    create_secret_from_env("hf-token-secret", "token", "HUGGING_FACE_HUB_TOKEN")
    
    # NeMo / LLM Secrets
    create_secret_from_env("llm-secrets", "openai-api-key", "OPENAI_API_KEY")
    
    # OPA Policy
    # Assuming policy file is at `src/governance/policy/finance_policy.rego` or similar.
    # We will look for it.
    policy_path = "src/governance/policy/finance_policy.rego"
    if not Path(policy_path).exists():
         # Fallback check
         if Path("deployment/finance_policy.rego").exists():
             policy_path = "deployment/finance_policy.rego"
    
    create_configmap_from_file("opa-policies", policy_path)

    # 6. Apply Kubernetes Manifests
    print("\n--- ☸️ Applying Kubernetes Manifests ---")
    k8s_dir = Path("deployment/k8s")
    
    manifests = list(k8s_dir.glob("*.yaml"))
    temp_dir = Path("deployment/k8s_rendered")
    temp_dir.mkdir(exist_ok=True)

    for manifest in manifests:
        if "tpl" in manifest.name: continue # Skip templates
        
        with open(manifest) as f:
            content = f.read()

        content = content.replace("${PROJECT_ID}", args.project_id)

        target_path = temp_dir / manifest.name
        with open(target_path, "w") as f:
            f.write(content)

    # Apply Rendered Manifests
    run_command(["kubectl", "apply", "-f", str(temp_dir)])

    # Cleanup
    shutil.rmtree(temp_dir)
    
    # 7. Wait for Ingress IP
    print("\n--- ⏳ Waiting for Ingress IP ---")
    print("Run: kubectl get ingress financial-advisor-ingress -w")

    print("\n✅ Deployment script completed successfully.")

if __name__ == "__main__":
    main()
