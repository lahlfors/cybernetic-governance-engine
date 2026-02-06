import os

from dotenv import load_dotenv

load_dotenv()

# Tiered Model Configuration (from .env)
# Fast path: Supervisor, Data Analyst, Execution Analyst
# Defaulting to Gemini 2.5 Flash-Lite (Jan 2026 Stable)
MODEL_FAST = os.getenv("MODEL_FAST", "gemini-2.5-flash-lite")

# Reasoning path: Risk Analyst, Verifier, Consensus (safety-critical)
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
    GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
    GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    PORT = int(os.getenv("PORT", 8080))

    # Data Stores
    FIRESTORE_DATABASE = os.getenv("FIRESTORE_DATABASE", "(default)")

    # Redis (Optional/Deprecated in Serverless mode)
    # If not set, app should fall back to MemorySaver
    REDIS_URL = os.getenv("REDIS_URL", None)

    # Observability
    LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://us.cloud.langfuse.com")
    LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
    LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")

    # Governance
    # OPA URL: If running in Cloud Run, this will be the URL of the OPA service
    OPA_URL = os.getenv("OPA_URL", "http://localhost:8181/v1/data/finance/decision")
    OPA_AUTH_TOKEN = os.getenv("OPA_AUTH_TOKEN")

    # NeMo Guardrails (Optional - currently using internal checks or sidecar)
    NEMO_URL = os.getenv("NEMO_URL", "http://nemo:8000/v1/guardrails/check")

    # Runtime Configuration Override (for Agent Engine)
    try:
        from config import runtime_config
        OPA_URL = getattr(runtime_config, "OPA_URL", OPA_URL)
        NEMO_URL = getattr(runtime_config, "NEMO_URL", NEMO_URL)
        OPA_AUTH_TOKEN = getattr(runtime_config, "OPA_AUTH_TOKEN", OPA_AUTH_TOKEN)
        GOOGLE_CLOUD_PROJECT = getattr(runtime_config, "GOOGLE_CLOUD_PROJECT", GOOGLE_CLOUD_PROJECT)
        GOOGLE_CLOUD_LOCATION = getattr(runtime_config, "GOOGLE_CLOUD_LOCATION", GOOGLE_CLOUD_LOCATION)
    except ImportError:
        pass

    @staticmethod
    def get_llm_config(profile="default"):
        return {
            "model": Config.DEFAULT_MODEL,
            "temperature": 0.0,
            "google_api_key": Config.GOOGLE_API_KEY
        }
