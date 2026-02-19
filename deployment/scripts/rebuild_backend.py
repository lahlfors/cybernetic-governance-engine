import os
import subprocess
from pathlib import Path

# Load .env manually to be 100% sure we have PROJECT_ID
env_path = Path(".env")
env_vars = {}
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env_vars[k.strip()] = v.strip().strip('"').strip("'")

project_id = env_vars.get("GOOGLE_CLOUD_PROJECT", "laah-cybernetics")
print(f"🏗️ Rebuilding Backend for {project_id} (Logging Fix)...")

image_uri = f"gcr.io/{project_id}/financial-advisor:latest"
# Use same build command as before
subprocess.run(["gcloud", "builds", "submit", "--tag", image_uri, "--project", project_id, "."], check=True)
print("✅ Backend Rebuilt.")

print("🔄 Restarting Deployment...")
subprocess.run(["kubectl", "rollout", "restart", "deployment/governed-financial-advisor", "-n", "governance-stack"], check=True)
print("✅ Deployment Restarted.")
