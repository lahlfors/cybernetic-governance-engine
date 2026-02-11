"""
Sovereign Configuration (Refactored)
"""
import os

from dotenv import load_dotenv

load_dotenv()

class Config:
    # --- MODEL IDENTIFIERS ---
    # Default: Llama 3.1 8B (The Workhorse)
    DEFAULT_MODEL = "meta-llama/Meta-Llama-3.1-8B-Instruct"

    # --- SPLIT-BRAIN INFRASTRUCTURE (Hardcoded Defaults) ---
    # Node A: The Brain (Reasoning/Planner) - Runs on dedicated L4 GPU
    VLLM_REASONING_API_BASE = os.getenv("VLLM_REASONING_API_BASE", "http://vllm-reasoning:8000/v1")
    MODEL_REASONING = os.getenv("MODEL_REASONING", DEFAULT_MODEL)

    # Node B: The Police (Governance/FSM) - Runs on CPU or Shared L4
    VLLM_FAST_API_BASE = os.getenv("VLLM_FAST_API_BASE", "http://vllm-governance:8000/v1")
    MODEL_FAST = os.getenv("MODEL_FAST", "meta-llama/Llama-3.2-3B-Instruct")

    # --- INFRASTRUCTURE ---
    PORT = int(os.getenv("PORT", 8080))

    # Data Stores
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Governance Sidecars
    OPA_URL = os.getenv("OPA_URL", "http://localhost:8181/v1/data/finance/allow")
    OPA_AUTH_TOKEN = os.getenv("OPA_AUTH_TOKEN")

    # Sandbox Sidecar (New)
    SANDBOX_URL = os.getenv("SANDBOX_URL", "http://localhost:8081/execute")

    @staticmethod
    def get_llm_config():
        return {
            "model": Config.MODEL_FAST,
            "base_url": Config.VLLM_FAST_API_BASE,
            "api_key": "EMPTY"
        }
