import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # --- MODEL IDENTIFIERS ---
    DEFAULT_MODEL = "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"

    # --- SPLIT-BRAIN INFRASTRUCTURE ---
    # Node A: The Brain (Reasoning/Planner)
    VLLM_REASONING_API_BASE = os.getenv("VLLM_REASONING_API_BASE", "http://vllm-reasoning:8000/v1")
    MODEL_REASONING = os.getenv("MODEL_REASONING", DEFAULT_MODEL)

    # Node B: The Police (Governance/FSM)
    VLLM_FAST_API_BASE = os.getenv("VLLM_FAST_API_BASE", "http://vllm-governance:8000/v1")
    MODEL_FAST = os.getenv("MODEL_FAST", "meta-llama/Llama-3.2-3B-Instruct")

    # --- INFRASTRUCTURE ---
    PORT = int(os.getenv("PORT", 8080))
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Sidecars
    OPA_URL = os.getenv("OPA_URL", "http://localhost:8181/v1/data/finance/allow")
    OPA_AUTH_TOKEN = os.getenv("OPA_AUTH_TOKEN")
    SANDBOX_URL = os.getenv("SANDBOX_URL", "http://localhost:8081/execute")
