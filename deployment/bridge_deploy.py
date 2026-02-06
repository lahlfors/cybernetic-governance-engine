#!/usr/bin/env python3
"""
Bridge Deployment Script
Orchestrates the build and deployment process:
1. Builds Docker images (Backend, Gateway, UI, NeMo).
2. Initializes Terraform.
3. Applies Terraform configuration with correct image variables.
"""

import argparse
import os
import sys
import subprocess
from pathlib import Path

# Add project root to sys.path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from deployment.lib.utils import load_dotenv, run_command

def check_gcloud_auth():
    """Checks if gcloud is authenticated."""
    try:
        run_command(["gcloud", "auth", "list", "--format", "value(account)"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("❌ gcloud not authenticated. Please run 'gcloud auth login' first.")
        sys.exit(1)

def build_images(project_id):
    """Builds all required Docker images."""
    print("\n--- 🏗️ Building Docker Images ---")
    
    # Define images 
    # Note: Gateway uses specific Dockerfile in src/gateway
    # NeMo uses Dockerfile.nemo at root
    images = [
        {"name": "Backend", "tag": f"gcr.io/{project_id}/financial-advisor:latest", "path": ".", "file": "Dockerfile"},
        {"name": "Gateway", "tag": f"gcr.io/{project_id}/gateway:latest", "path": ".", "file": "src/gateway/Dockerfile"},
        {"name": "UI", "tag": f"gcr.io/{project_id}/financial-advisor-ui:latest", "path": "ui", "file": "Dockerfile"},
        {"name": "NeMo", "tag": f"gcr.io/{project_id}/nemo-guardrails-service:latest", "path": ".", "file": "Dockerfile.nemo"},
    ]

    for img in images:
        print(f"\n🚀 Building {img['name']} ({img['tag']})...")
        
        # Use cloudbuild.yaml for custom Dockerfile paths to ensure clean build context
        if img["file"] != "Dockerfile":
             cloudbuild_yaml = f"""
steps:
- name: 'gcr.io/cloud-builders/docker'
  args: ['build', '-t', '{img['tag']}', '-f', '{img['file']}', '.']
images:
- '{img['tag']}'
"""
             cb_file = Path(f"cloudbuild_{img['name'].lower()}.yaml")
             with open(cb_file, "w") as f:
                 f.write(cloudbuild_yaml)
             try:
                 # Submit with config
                 run_command(["gcloud", "builds", "submit", "--config", str(cb_file), "--project", project_id, img["path"]])
             finally:
                 if cb_file.exists(): cb_file.unlink()
        
        else:
             # Standard build
             run_command(["gcloud", "builds", "submit", "--tag", img["tag"], "--project", project_id, img["path"]])

def run_terraform(project_id):
    """Runs Terraform init and apply."""
    print("\n--- 🌍 Running Terraform ---")
    tf_dir = Path("deployment/terraform")
    
    # Init
    print("Initializing Terraform...")
    run_command(["terraform", "init"], cwd=tf_dir)
    
    # Apply
    print("Applying Terraform Configuration...")
    # Pass Gateway Image explicitly
    gateway_image = f"gcr.io/{project_id}/gateway:latest"
    
    # We use -auto-approve as this is a "bridge" script meant to execute the deployment
    run_command([
        "terraform", "apply", "-auto-approve",
        f"-var=project_id={project_id}",
        f"-var=gateway_image={gateway_image}"
    ], cwd=tf_dir)

def main():
    parser = argparse.ArgumentParser(description="Bridge Deploy: Build Images & Run Terraform")
    parser.add_argument("--project-id", help="Google Cloud Project ID")
    args = parser.parse_args()

    load_dotenv()
    
    project_id = args.project_id or os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("TF_VAR_project_id")
    
    if not project_id:
        # Try to guess from gcloud config
        try:
             res = subprocess.run(["gcloud", "config", "get-value", "project"], capture_output=True, text=True)
             project_id = res.stdout.strip()
        except:
             pass
    
    if not project_id:
        print("❌ Project ID not found. Set GOOGLE_CLOUD_PROJECT or pass --project-id.")
        sys.exit(1)

    print(f"🔹 Project ID: {project_id}")
    
    check_gcloud_auth()
    build_images(project_id)
    run_terraform(project_id)

if __name__ == "__main__":
    main()
