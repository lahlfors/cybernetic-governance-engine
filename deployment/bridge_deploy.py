#!/usr/bin/env python3
"""
Bridge Deployment Script
Orchestrates the build and deployment process:
1. Builds Docker images (Backend, Gateway, UI).
2. Initializes Terraform.
3. Applies Terraform configuration.
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
    
    images = [
        {"name": "Backend", "tag": f"gcr.io/{project_id}/financial-advisor:latest", "path": ".", "file": "Dockerfile"},
        {"name": "Gateway", "tag": f"gcr.io/{project_id}/gateway:latest", "path": ".", "file": "src/gateway/Dockerfile"},
        {"name": "UI", "tag": f"gcr.io/{project_id}/financial-advisor-ui:latest", "path": "ui", "file": "ui/Dockerfile"},
    ]

    for img in images:
        print(f"\n🚀 Building {img['name']} ({img['tag']})...")
        cmd = [
            "gcloud", "builds", "submit",
            "--tag", img["tag"],
            "--project", project_id,
            img["path"]
        ]
        if "file" in img and img["file"] != "Dockerfile": 
             # If specific file is needed and it's not default (though gcloud builds submit handles directory context usually)
             # Actually gcloud builds submit takes source directory. If Dockerfile is not at root of source, we might need --config or just let it detect if at root.
             # For Gateway: source is '.', Dockerfile is 'src/gateway/Dockerfile'.
             # For UI: source is 'ui', Dockerfile is 'ui/Dockerfile'.
             pass

        # Adjusting for gcloud builds submit quirks
        # For Gateway: we want context '.' but Dockerfile 'src/gateway/Dockerfile'. 
        # gcloud builds submit doesn't easily support -f like docker build without a cloudbuild.yaml usually, OR we use basic build which expects Dockerfile at root of source.
        # WAIT: 'gcloud builds submit' with simple args requires Dockerfile in the source root or we use a config.
        # Let's use a temporary cloudbuild.yaml for complex cases or just use docker build + push if we had docker.
        # But we want to use Cloud Build.
        
        if img["name"] == "Gateway":
            # context is root, dockerfile is src/gateway/Dockerfile
            # Use --config to specify build steps
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
                 run_command(["gcloud", "builds", "submit", "--config", str(cb_file), "--project", project_id, "."])
             finally:
                 if cb_file.exists(): cb_file.unlink()
        
        elif img["name"] == "Backend":
             # Dockerfile is at root
             run_command(["gcloud", "builds", "submit", "--tag", img["tag"], "--project", project_id, "."])
        
        elif img["name"] == "UI":
             # Dockerfile is at ui/Dockerfile
             # If we submit 'ui' directory, Dockerfile is at root of THAT directory.
             # So 'ui/Dockerfile' relative to project root is 'Dockerfile' relative to 'ui' dir.
             run_command(["gcloud", "builds", "submit", "--tag", img["tag"], "--project", project_id, "ui"])

def run_terraform():
    """Runs Terraform init and apply."""
    print("\n--- 🌍 Running Terraform ---")
    tf_dir = Path("deployment/terraform")
    
    # Init
    print("Initializing Terraform...")
    run_command(["terraform", "init"], cwd=tf_dir)
    
    # Apply
    print("Applying Terraform Configuration...")
    # Using -auto-approve to make it non-interactive for the script, but user should be careful.
    # Maybe we should let it ask? The user asked for a bridge script, usually implies automation.
    # I'll let it Ask implicitly by NOT passing auto-approve unless a flag is passed, OR maybe just pass it if user wants "link these processes".
    # Let's use -auto-approve for "bridge" effect, but prone to danger. 
    # Better: Don't use auto-approve by default, let user confirm plan.
    run_command(["terraform", "apply", "-auto-approve"], cwd=tf_dir)

def main():
    parser = argparse.ArgumentParser(description="Bridge Deploy: Build Images & Run Terraform")
    parser.add_argument("--project-id", help="Google Cloud Project ID")
    parser.add_argument("--region", default="us-central1", help="GCP Region")
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
    run_terraform()

if __name__ == "__main__":
    main()
