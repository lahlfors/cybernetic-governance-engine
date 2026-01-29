
import subprocess
from .utils import run_command

def enable_apis(project_id):
    """Enables necessary Google Cloud APIs."""
    print("\n--- 🛠️ Enabling APIs ---")
    apis = [
        "redis.googleapis.com",
        "aiplatform.googleapis.com",
        "secretmanager.googleapis.com",
        "run.googleapis.com",
        "cloudbuild.googleapis.com",
        "container.googleapis.com" # Required for GKE/Kubectl
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
