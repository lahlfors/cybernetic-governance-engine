import subprocess
import time
import os

PROJECT_ID = "laah-cybernetics"
IMAGE_NAME = "gcr.io/laah-cybernetics/financial-advisor"

def run(cmd):
    print(f"Running: {cmd}")
    subprocess.check_call(cmd, shell=True)

print("🏗️ Rebuilding Backend...")
# Ensure we are in the root
cwd = os.getcwd()
print(f"CWD: {cwd}")

run(f"gcloud builds submit --tag {IMAGE_NAME} .")

print("🔄 Restarting Deployment...")
run("kubectl rollout restart deployment/governed-financial-advisor -n governance-stack")
print("Waiting for rollout...")
run("kubectl rollout status deployment/governed-financial-advisor -n governance-stack")

print("✅ Backend Rebuilt and Restarted.")
