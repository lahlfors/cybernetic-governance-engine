import os
import subprocess
from pathlib import Path

# Load .env manually to be 100% sure
env_path = Path(".env")
env_vars = {}
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env_vars[k.strip()] = v.strip().strip('"').strip("'")

print(f"✅ Loaded {len(env_vars)} vars from .env")
print(f"LANGCHAIN_API_KEY from .env: {env_vars.get('LANGCHAIN_API_KEY')}")

# Secrets to create
advisor_secrets = {
    "LANGCHAIN_TRACING_V2": env_vars.get("LANGCHAIN_TRACING_V2", "true"),
    "LANGCHAIN_ENDPOINT": env_vars.get("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com"),
    "LANGCHAIN_API_KEY": env_vars.get("LANGCHAIN_API_KEY", ""),
    "LANGCHAIN_PROJECT": env_vars.get("LANGCHAIN_PROJECT", "financial-advisor"),
    "LANGSMITH_TRACING": env_vars.get("LANGCHAIN_TRACING_V2", "true"), # Alias
    "LANGSMITH_ENDPOINT": env_vars.get("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com"), # Alias
    "LANGSMITH_API_KEY": env_vars.get("LANGCHAIN_API_KEY", ""), # Alias
    "LANGSMITH_PROJECT": env_vars.get("LANGCHAIN_PROJECT", "financial-advisor"), # Alias
    "ALPHAVANTAGE_API_KEY": env_vars.get("ALPHAVANTAGE_API_KEY", "")
}

# Construct command
cmd = ["kubectl", "create", "secret", "generic", "advisor-secrets", "--dry-run=client", "-o", "yaml", "-n", "governance-stack"]
for k, v in advisor_secrets.items():
    if v:
        cmd.append(f"--from-literal={k}={v}")

print("🚀 Creating advisor-secrets...")
try:
    secret_yaml = subprocess.check_output(cmd, text=True)
    subprocess.run(["kubectl", "apply", "-f", "-"], input=secret_yaml, text=True, check=True)
    print("✅ advisor-secrets updated.")
except subprocess.CalledProcessError as e:
    print(f"❌ Failed to update secrets: {e}")
    exit(1)

# Now trigger build of backend
project_id = env_vars.get("GOOGLE_CLOUD_PROJECT", "laah-cybernetics")
print(f"🏗️ Rebuilding Backend for {project_id} (to remove baked-in .env)...")
image_uri = f"gcr.io/{project_id}/financial-advisor:latest"
subprocess.run(["gcloud", "builds", "submit", "--tag", image_uri, "--project", project_id, "."], check=True)
print("✅ Backend Rebuilt.")

# Restart Deployment
print("🔄 Restarting Deployment...")
subprocess.run(["kubectl", "rollout", "restart", "deployment/governed-financial-advisor", "-n", "governance-stack"], check=True)
print("✅ Deployment Restarted.")
