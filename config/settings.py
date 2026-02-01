import os

from dotenv import load_dotenv

load_dotenv()

# Tiered Model Configuration (from .env)

# --- FAST PATH (Control Plane) ---
# Used for: Routing, JSON formatting, Simple Execution
# Recommended: meta-llama/Llama-3.1-8B-Instruct (Open Weights)
MODEL_FAST = os.getenv("MODEL_FAST", "meta-llama/Llama-3.1-8B-Instruct")
VLLM_FAST_API_BASE = os.getenv("VLLM_FAST_API_BASE", "http://localhost:8000/v1")

# --- REASONING PATH (Reasoning Plane) ---
# Used for: Risk Analysis, Strategic Planning, Evaluation (STPA)
# Recommended: meta-llama/Llama-3.1-70B-Instruct (Open Weights)
MODEL_REASONING = os.getenv("MODEL_REASONING", "meta-llama/Llama-3.1-70B-Instruct")
VLLM_REASONING_API_BASE = os.getenv("VLLM_REASONING_API_BASE", "http://localhost:8001/v1") # Default to port 8001 for separate instance

# Consensus Engine: Separate model for multi-agent debate (can use different provider)
MODEL_CONSENSUS = os.getenv("MODEL_CONSENSUS", MODEL_REASONING)

# Legacy alias for backward compatibility
MODEL_NAME = MODEL_FAST

class Config:
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "EMPTY") # Default to EMPTY for local vLLM
    DEFAULT_MODEL = MODEL_FAST

    # Cloud Run / Infrastructure
    GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "sovereign-stack")
    GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "local")
    PORT = int(os.getenv("PORT", 8080))

    # Data Stores
    FIRESTORE_DATABASE = os.getenv("FIRESTORE_DATABASE", "(default)")
    # Build REDIS_URL from host/port for compatibility with K8s deployment
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = os.getenv("REDIS_PORT", "6379")
    REDIS_URL = os.getenv("REDIS_URL", f"redis://{REDIS_HOST}:{REDIS_PORT}")

    # Governance
    OPA_URL = os.getenv("OPA_URL", "http://localhost:8181/v1/data/finance/decision")
    OPA_AUTH_TOKEN = os.getenv("OPA_AUTH_TOKEN")
    NEMO_URL = os.getenv("NEMO_URL", "http://nemo:8000/v1/guardrails/check")

    # Model Endpoints
    VLLM_FAST_API_BASE = VLLM_FAST_API_BASE
    VLLM_REASONING_API_BASE = VLLM_REASONING_API_BASE

    # Model Names
    MODEL_REASONING = MODEL_REASONING

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
        """
        Returns the LLM configuration.
        Note: The 'base_url' here is primarily for standard/legacy clients.
        The HybridClient (Gateway) manages its own routing and ignores this
        base_url when switching between Fast/Reasoning endpoints.
        """
        return {
            "model": Config.DEFAULT_MODEL,
            "temperature": 0.0,
            "google_api_key": Config.GOOGLE_API_KEY,
            "base_url": Config.VLLM_FAST_API_BASE
        }
