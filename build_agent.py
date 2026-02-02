
import os
import tarfile
import cloudpickle
from src.governed_financial_advisor.reasoning_engine import FinancialAdvisorEngine

# Configuration
ARTIFACTS_DIR = "deployment/artifacts"
PICKLE_FILE = os.path.join(ARTIFACTS_DIR, "pickle.pkl")
REQUIREMENTS_FILE = os.path.join(ARTIFACTS_DIR, "requirements.txt")
DEPENDENCIES_FILE = os.path.join(ARTIFACTS_DIR, "dependencies.tar.gz")

# Ensure artifacts directory exists
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

def create_pickle():
    print(f"Creating {PICKLE_FILE}...")
    agent = FinancialAdvisorEngine()
    # Serialize the agent
    with open(PICKLE_FILE, "wb") as f:
        cloudpickle.dump(agent, f)
    print("Pickle created.")

def create_requirements():
    print(f"Creating {REQUIREMENTS_FILE}...")
    requirements = [
        "google-cloud-aiplatform[agent-engines]",
        "langchain-google-vertexai",
        "langchain-google-genai",
        "langgraph",
        "langgraph-checkpoint-redis",
        "redis",
        "pydantic",
        "google-auth",
        "yfinance",
        "pandas",
        "httpx",
        "python-json-logger",
        "nest_asyncio",
        "google-adk",
        "google-cloud-secret-manager"
    ]
    with open(REQUIREMENTS_FILE, "w") as f:
        f.write("\n".join(requirements))
    print("Requirements created.")

def create_dependencies():
    print(f"Creating {DEPENDENCIES_FILE}...")
    with tarfile.open(DEPENDENCIES_FILE, "w:gz") as tar:
        # Add src directory
        if os.path.exists("src"):
            print("Adding src/ to dependencies...")
            tar.add("src", arcname="src")
        if os.path.exists("config"):
            print("Adding config/ to dependencies...")
            tar.add("config", arcname="config")
    print("Dependencies created.")

if __name__ == "__main__":
    create_pickle()
    create_requirements()
    create_dependencies()
    print("Build complete.")
