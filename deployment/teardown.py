#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path

# Ensure project root is in sys.path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from deployment.lib.config import load_config

def run_command(command, check=True):
    print(f"🚀 Running: {' '.join(command)}")
    try:
        subprocess.run(command, check=check)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        if check:
            sys.exit(1)

def main():
    # Load config defaults
    config = load_config()
    default_region = config.get("project", {}).get("region", "us-central1")
    default_zone = config.get("project", {}).get("zone")
    default_cluster = config.get("cluster", {}).get("name", "governance-cluster")

    parser = argparse.ArgumentParser(description="Teardown Cybernetic Governance Engine Resources")
    parser.add_argument("--project-id", required=True, help="Google Cloud Project ID")
    parser.add_argument("--region", default=default_region, help=f"GCP Region (default: {default_region})")
    parser.add_argument("--zone", default=default_zone, help="GCP Zone (optional, overrides region for GKE)")
    parser.add_argument("--cluster-name", default=default_cluster, help="GKE Cluster Name")
    parser.add_argument("--service-name", default="financial-advisor-ui", help="Cloud Run UI Service Name")
    
    args = parser.parse_args()
    
    print("⚠️  STARTING TEARDOWN ⚠️")
    print("This will delete the GKE cluster, Cloud Run service, and Secret Manager secrets.")
    
    # 1. Delete Cloud Run Service
    print("\n--- 🗑️ Deleting Cloud Run Services ---")
    services = [args.service_name, "governed-financial-advisor"]
    for svc in services:
        run_command([
            "gcloud", "run", "services", "delete", svc,
            "--region", args.region,
            "--project", args.project_id,
            "--quiet"
        ], check=False)

    # 2. Delete GKE Cluster
    print("\n--- 🗑️ Deleting GKE Cluster ---")
    location_flag = "--zone" if args.zone else "--region"
    location_value = args.zone if args.zone else args.region
    run_command([
        "gcloud", "container", "clusters", "delete", args.cluster_name,
        location_flag, location_value,
        "--project", args.project_id,
        "--quiet"
    ], check=False)

    # 3. Delete Secrets
    print("\n--- 🗑️ Deleting Secrets ---")
    secrets = ["opa-auth-token", "system-authz-policy", "finance-policy-rego", "opa-configuration", "hf-token-secret"]
    for s in secrets:
        run_command([
            "gcloud", "secrets", "delete", s,
            "--project", args.project_id,
            "--quiet"
        ], check=False)

    # 4. Delete Network Resources
    print("\n--- 🗑️ Deleting Network Resources (NAT/Router) ---")
    router_name = f"nat-router-{args.region}"
    nat_name = f"nat-config-{args.region}"
    
    run_command([
        "gcloud", "compute", "routers", "nats", "delete", nat_name,
        "--router", router_name,
        "--region", args.region,
        "--project", args.project_id,
        "--quiet"
    ], check=False)
    
    run_command([
        "gcloud", "compute", "routers", "delete", router_name,
        "--region", args.region,
        "--project", args.project_id,
        "--quiet"
    ], check=False)

    # 5. Delete Redis Instance
    print("\n--- 🗑️ Deleting Redis Instance ---")
    run_command([
        "gcloud", "redis", "instances", "delete", "financial-advisor-redis",
        "--region", args.region,
        "--project", args.project_id,
        "--quiet"
    ], check=False)

    print("\n✅ Teardown Complete. Verify in Cloud Console.")

if __name__ == "__main__":
    main()
