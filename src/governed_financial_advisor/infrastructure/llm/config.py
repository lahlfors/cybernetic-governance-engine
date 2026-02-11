import logging
from typing import Any

# Since google.adk.models.lite_llm depends on litellm which we removed,
# we need to provide a mock or alternative if we want to keep using ADK agents.
# However, the ADK agents (e.g. data_analyst) import `Agent` from `google.adk`.
# `google.adk` likely still depends on `litellm`.
# If we removed `litellm` from requirements, `google.adk` might break.
# Let's check pyproject.toml again.
# pyproject.toml has `google-adk>=0.11.2`.
# If `google-adk` requires `litellm`, removing `litellm` from our direct deps
# doesn't remove it from the environment if `google-adk` pulls it in.
# But we should try to make `get_adk_model` use our GatewayClient if possible,
# or at least configure it to point to our Sovereign Gateway.
# The `GatewayClient` logic is:
# Node A (Reasoning): http://vllm-reasoning:8000/v1
# Node B (Governance): http://vllm-governance:8000/v1
# ADK's `LiteLlm` uses `litellm` under the hood.
# We can configure it to point to `vllm-governance` by default for standard agents,
# and maybe `vllm-reasoning` for specific ones.
# BUT, the prompt said "Refactor src/gateway/core/llm.py to GatewayClient... Drop litellm."
# It didn't explicitly say "Remove google-adk".
# The `data_analyst_agent` uses `google.adk.Agent`.
# So we must keep `google-adk` working.
from google.adk.models.lite_llm import LiteLlm

from config.settings import Config

logger = logging.getLogger(__name__)

def get_adk_model(
    model_name: str | None = None,
    # These args might be passed by legacy code, but we should prefer Config
    api_base: str | None = None,
    api_key: str = "EMPTY",
    **kwargs: Any
) -> LiteLlm:
    """
    Returns a configured ADK LiteLlm model instance for Sovereign vLLM.
    
    Routes to the Governance Node (Fast) by default for standard ADK agents.
    If 'reasoning' is in the model name, routes to Reasoning Node.
    """
    # Default to Governance Node (Fast)
    target_base_url = Config.VLLM_FAST_API_BASE
    target_model = Config.MODEL_FAST

    # Check if requested model implies reasoning
    if model_name and (model_name == Config.MODEL_REASONING or "reasoning" in model_name.lower()):
        target_base_url = Config.VLLM_REASONING_API_BASE
        target_model = Config.MODEL_REASONING
    elif model_name:
        target_model = model_name

    # LiteLLM needs 'openai/' prefix for OpenAI-compatible endpoints
    # if the model name doesn't start with a known provider.
    litellm_model_name = target_model
    if not litellm_model_name.startswith("openai/") and "gpt" not in litellm_model_name:
         litellm_model_name = f"openai/{target_model}"

    logger.info(f"Creating ADK Model: {litellm_model_name} -> {target_base_url}")

    return LiteLlm(
        model=litellm_model_name,
        api_base=target_base_url,
        api_key=api_key,
        **kwargs
    )
