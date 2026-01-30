import os

from dotenv import load_dotenv

load_dotenv()

# Tiered Model Configuration (from .env)
# Fast path: Supervisor, Data Analyst, Execution Analyst
# Defaulting to Gemini 2.5 Flash-Lite (Jan 2026 Stable)
MODEL_FAST = os.getenv("MODEL_FAST", "gemini-2.5-flash-lite")

# Reasoning path: Risk Analyst, Verifier (safety-critical)
# Defaulting to Gemini 2.5 Pro (Jan 2026 Stable)
MODEL_REASONING = os.getenv("MODEL_REASONING", "gemini-2.5-pro")

# Consensus Engine: Separate model for multi-agent debate (can use different provider)
MODEL_CONSENSUS = os.getenv("MODEL_CONSENSUS", MODEL_REASONING)

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
    # Build REDIS_URL from host/port for compatibility with K8s deployment
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = os.getenv("REDIS_PORT", "6379")
    REDIS_URL = os.getenv("REDIS_URL", f"redis://{REDIS_HOST}:{REDIS_PORT}")

    # Governance
    OPA_URL = os.getenv("OPA_URL", "http://localhost:8181/v1/data/finance/decision")
    OPA_AUTH_TOKEN = os.getenv("OPA_AUTH_TOKEN")

    @staticmethod
    def get_llm_config(profile="default"):
        return {
            "model": Config.DEFAULT_MODEL,
            "temperature": 0.0,
            "google_api_key": Config.GOOGLE_API_KEY
        }
