import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # --- MODEL IDENTIFIERS ---
    # FORCE DeepSeek as the default for Reasoning
    DEFAULT_REASONING_MODEL = "openai/deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
    
    # Node A: The Brain (Reasoning/Planner)
    VLLM_REASONING_API_BASE = os.getenv("VLLM_REASONING_API_BASE", "http://vllm-reasoning:8000/v1")
    MODEL_REASONING = os.getenv("MODEL_REASONING", DEFAULT_REASONING_MODEL)

    # Node B: The Police (Governance/FSM)
    # vLLM / Model Serving
    VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
    VLLM_API_KEY = os.getenv("VLLM_API_KEY", "EMPTY")
    
    # Gateway Configuration
    GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8080")
    GATEWAY_API_BASE = f"{GATEWAY_URL}/v1" # Standard OpenAI-compatible endpoint
    MCP_SERVER_SSE_URL = os.getenv("MCP_SERVER_SSE_URL", f"{GATEWAY_URL}/mcp/sse")
    VLLM_FAST_API_BASE = os.getenv("VLLM_FAST_API_BASE", "http://vllm-service:8000/v1")
    MODEL_FAST = os.getenv("MODEL_FAST", "openai/meta-llama/Meta-Llama-3.1-8B-Instruct")
    MODEL_CONSENSUS = os.getenv("MODEL_CONSENSUS", MODEL_REASONING)

    MAX_TOKENS = int(os.getenv("MAX_TOKENS", 8192))
    
    # --- INFRASTRUCTURE ---
    GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
    GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    PORT = int(os.getenv("PORT", 8080))
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Sidecars
    OPA_URL = os.getenv("OPA_URL", "http://localhost:8181/v1/data/finance/allow")
    OPA_AUTH_TOKEN = os.getenv("OPA_AUTH_TOKEN")
    SANDBOX_URL = os.getenv("SANDBOX_URL", "http://localhost:8081/execute")

    # --- NEW: GKE INFERENCE GATEWAY ---
    # If this is set, GatewayClient will route all requests here.
    # Otherwise, it falls back to the split-brain URLs above.
    VLLM_GATEWAY_URL = os.getenv("VLLM_GATEWAY_URL")

    # --- LangSmith ---
    LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "true")
    LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "financial-advisor")

# Backward compatibility & Module-level access
MODEL_NAME = Config.DEFAULT_REASONING_MODEL
MODEL_FAST = Config.MODEL_FAST
MODEL_REASONING = Config.MODEL_REASONING
MODEL_CONSENSUS = Config.MODEL_CONSENSUS
VLLM_FAST_API_BASE = Config.VLLM_FAST_API_BASE
VLLM_REASONING_API_BASE = Config.VLLM_REASONING_API_BASE
VLLM_GATEWAY_URL = Config.VLLM_GATEWAY_URL
GATEWAY_API_BASE = Config.GATEWAY_API_BASE
PORT = Config.PORT
REDIS_URL = Config.REDIS_URL
OPA_URL = Config.OPA_URL
OPA_AUTH_TOKEN = Config.OPA_AUTH_TOKEN
SANDBOX_URL = Config.SANDBOX_URL
