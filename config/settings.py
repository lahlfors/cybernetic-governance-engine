import os
from dotenv import load_dotenv

load_dotenv()

# Tiered Model Configuration (from .env)
# Fast path: Supervisor, Data Analyst, Execution Analyst
MODEL_FAST = os.getenv("MODEL_FAST", "gemini-2.0-flash")

# Reasoning path: Risk Analyst, Verifier, Consensus (safety-critical)
MODEL_REASONING = os.getenv("MODEL_REASONING", "gemini-2.5-pro")

# Legacy alias for backward compatibility
MODEL_NAME = MODEL_FAST

class Config:
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    DEFAULT_MODEL = MODEL_FAST

    # Cloud Run / Infrastructure
    GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "laah-cybernetics")
    GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    PORT = int(os.getenv("PORT", 8080))

    # Data Stores
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Governance (Architecture II: In-Process Wasm)
    # Replaced OPA_URL/OPA_AUTH_TOKEN with local file path
    OPA_WASM_PATH = os.getenv("OPA_WASM_PATH", "policy.wasm")

    @staticmethod
    def get_llm_config(profile="default"):
        return {
            "model": Config.DEFAULT_MODEL,
            "temperature": 0.0,
            "google_api_key": Config.GOOGLE_API_KEY
        }
