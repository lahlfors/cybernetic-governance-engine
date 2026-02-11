import os
import logging
from typing import Optional, Any

from google.adk.models.lite_llm import LiteLlm

# Default values suitable for the vLLM setup
DEFAULT_VLLM_BASE_URL = "http://localhost:8000/v1"
DEFAULT_MODEL_NAME = "openai/meta-llama/Meta-Llama-3.1-8B-Instruct"

logger = logging.getLogger(__name__)

def get_adk_model(
    model_name: Optional[str] = None,
    api_base: Optional[str] = None,
    api_key: str = "EMPTY",
    **kwargs: Any
) -> LiteLlm:
    """
    Returns a configured ADK LiteLlm model instance for vLLM.
    
    Args:
        model_name: The model name to use. Defaults to GUARDRAILS_MODEL_NAME env var or default.
        api_base: The base URL for the API. Defaults to VLLM_BASE_URL env var or default.
        api_key: The API key. Defaults to VLLM_API_KEY env var or "EMPTY".
        **kwargs: Additional arguments to pass to LiteLlm constructor.
    """
    # Resolve configuration
    base_url = api_base or os.environ.get("VLLM_BASE_URL", DEFAULT_VLLM_BASE_URL)
    model = model_name or os.environ.get("GUARDRAILS_MODEL_NAME", DEFAULT_MODEL_NAME)
    key = os.environ.get("VLLM_API_KEY", api_key)
    
    # Ensure model name implies OpenAI compatibility if needed usually explicitly "openai/..." for litellm
    # But often vLLM endpoints just take the model name requested or ignore it if only one model is served.
    # Litellm might need 'openai/' prefix to know it's an OpenAI-compatible endpoint if not using a specific provider alias.
    if not model.startswith("openai/") and "gpt" not in model:
        # Heuristic: if it looks like a HF path, prefix with openai/ for litellm to treat as openai-compatible
        model = f"openai/{model}"
        
    logger.info(f"Creating ADK LiteLlm model: {model} at {base_url}")
    
    return LiteLlm(
        model=model,
        api_base=base_url,
        api_key=key,
        **kwargs
    )
