import argparse
import os
import tarfile
import cloudpickle
from pathlib import Path
import sys
import importlib

# Ensure project root is in path
# Assumes script is in scripts/ directory
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)

def main():
    parser = argparse.ArgumentParser(description="Prepare Agent for Deployment")
    parser.add_argument("--nemo-url", required=True, help="URL of NeMo Service")
    parser.add_argument("--opa-url", required=True, help="URL of OPA Service")
    parser.add_argument("--opa-auth-token", required=True, help="OPA Auth Token")
    parser.add_argument("--project-id", required=True, help="Google Cloud Project ID")
    parser.add_argument("--location", required=True, help="Google Cloud Region")

    args = parser.parse_args()

    print(f"🚀 Preparing Agent Artifacts...")
    print(f"   NeMo URL: {args.nemo_url}")
    print(f"   OPA URL: {args.opa_url}")

    # 1. Generate config/runtime_config.py
    config_dir = Path("config")
    config_dir.mkdir(exist_ok=True)
    runtime_config_path = config_dir / "runtime_config.py"

    with open(runtime_config_path, "w") as f:
        f.write(f'OPA_URL = "{args.opa_url}"\n')
        f.write(f'NEMO_URL = "{args.nemo_url}"\n')
        f.write(f'OPA_AUTH_TOKEN = "{args.opa_auth_token}"\n')
        f.write(f'GOOGLE_CLOUD_PROJECT = "{args.project_id}"\n')
        f.write(f'GOOGLE_CLOUD_LOCATION = "{args.location}"\n')

    print(f"✅ Generated {runtime_config_path}")

    # 2. Pickle the Agent
    # Import AFTER writing config so Config picks it up
    try:
        import config.settings
        importlib.reload(config.settings)

        from src.agents.governed_trader.agent import create_governed_trader_agent
        agent = create_governed_trader_agent()

        with open("agent.pkl", "wb") as f:
            cloudpickle.dump(agent, f)
        print("✅ Generated agent.pkl")

    except Exception as e:
        print(f"❌ Failed to pickle agent: {e}")
        # Print more info
        import traceback
        traceback.print_exc()
        raise e

    # 3. Create requirements.txt
    # Include dependencies needed by the agent in the runtime
    requirements = [
        "google-cloud-aiplatform[agent_engines,adk]>=1.93.0",
        "cloudpickle>=3.0",
        "google-adk>=0.14.0",
        "pydantic",
        "httpx",
        "python-dotenv",
        "opentelemetry-api",
        "opentelemetry-sdk",
        "nest-asyncio"
    ]

    with open("requirements.txt", "w") as f:
        for req in requirements:
            f.write(req + "\n")
    print("✅ Generated requirements.txt")

    # 4. Create dependencies.tar.gz
    # Must include src/ and config/
    with tarfile.open("dependencies.tar.gz", "w:gz") as tar:
        tar.add("src", arcname="src")
        tar.add("config", arcname="config")
    print("✅ Generated dependencies.tar.gz")

if __name__ == "__main__":
    main()
