"""
Factory for creating NeMo Guardrails manager with vLLM/Llama support.
"""
import logging
import os
from typing import Any

import nest_asyncio
from langchain_core.language_models.llms import LLM
from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.context import streaming_handler_var
from nemoguardrails.llm.providers import register_llm_provider
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from src.governed_financial_advisor.infrastructure.telemetry.nemo_exporter import NeMoOTelCallback
from src.governed_financial_advisor.infrastructure.config_manager import config_manager

# Configure Logging
logger = logging.getLogger("NeMoManager")
tracer = trace.get_tracer(__name__)

class VLLMLLM(LLM):
    """Custom LangChain-compatible wrapper for vLLM using LiteLLM."""

    model: str = config_manager.get("GUARDRAILS_MODEL_NAME", "meta-llama/Meta-Llama-3.1-8B-Instruct")
    api_base: str = config_manager.get("VLLM_BASE_URL", "http://localhost:8000/v1")
    api_key: str = config_manager.get("VLLM_API_KEY", "EMPTY")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        print(f"DEBUG: VLLMLLM initialized with model={self.model}, base={self.api_base}")

    @property
    def _llm_type(self) -> str:
        return "vllm"

    def _call(self, prompt: str, stop: list[str] | None = None, **kwargs: Any) -> str:
        """Call the vLLM model via LiteLLM."""
        try:
            import litellm
            
            # Ensure model has openai/ prefix if needed by litellm for generic vLLM
            # But usually for vLLM we can just use the model name if we pass api_base.
            # However, litellm recommends 'openai/<model_name>' for generic openai-compatible endpoints.
            model_id = self.model
            if not model_id.startswith("openai/"):
                model_id = f"openai/{model_id}"

            print(f"DEBUG: Calling vLLM via litellm... model={model_id} base={self.api_base}")
            
            response = litellm.completion(
                model=model_id,
                api_base=self.api_base,
                api_key=self.api_key,
                messages=[{"role": "user", "content": prompt}],
                stop=stop,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Failed to call vLLM: {e}")
            return f"Error calling vLLM: {e}"

    async def _acall(self, prompt: str, stop: list[str] | None = None, **kwargs: Any) -> str:
        """Async call to the vLLM model via LiteLLM."""
        try:
            import litellm
            
            model_id = self.model
            if not model_id.startswith("openai/"):
                model_id = f"openai/{model_id}"

            print(f"DEBUG: Async Calling vLLM via litellm... model={model_id} base={self.api_base}")
            
            response = await litellm.acompletion(
                model=model_id,
                api_base=self.api_base,
                api_key=self.api_key,
                messages=[{"role": "user", "content": prompt}],
                stop=stop,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Failed to call vLLM (async): {e}")
            return f"Error calling vLLM: {e}"

    @property
    def _identifying_params(self) -> dict:
        return {"model": self.model, "api_base": self.api_base}


def create_nemo_manager(config_path: str = "config/rails") -> LLMRails:
    """
    Creates and initializes a NeMo Guardrails manager with vLLM support.
    """
    try:
        nest_asyncio.apply()
    except Exception:
        pass

    # Register our custom provider
    register_llm_provider("vllm_llama", VLLMLLM)
    
    # Resolve config path
    if not os.path.exists(config_path):
        cwd_path = os.path.join(os.getcwd(), config_path)
        if os.path.exists(cwd_path):
            config_path = cwd_path
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            possible_path = os.path.join(base_dir, "rails_config")
            if os.path.exists(possible_path):
                config_path = possible_path

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"NeMo Guardrails config not found at: {config_path}")

    print(f"DEBUG: Loading NeMo config from {config_path}")
    config = RailsConfig.from_path(config_path)
    
    rails = LLMRails(config)

    # Explicitly register actions
    try:
        from src.governed_financial_advisor.governance.nemo_actions import (
            check_approval_token,
            check_data_latency,
            check_drawdown_limit,
            check_slippage_risk,
            check_atomic_execution,
        )
        rails.register_action(check_approval_token, "check_approval_token")
        rails.register_action(check_data_latency, "check_data_latency")
        rails.register_action(check_drawdown_limit, "check_drawdown_limit")
        rails.register_action(check_slippage_risk, "check_slippage_risk")
        rails.register_action(check_atomic_execution, "check_atomic_execution")
        logger.info("✅ NeMo actions registered successfully")
    except ImportError as e:
        logger.warning(f"⚠️ Could not import NeMo actions: {e}")

    return rails

# --- Adapters ---

def load_rails() -> LLMRails:
    """Wrapper to maintain consistency with new design."""
    return create_nemo_manager()

async def validate_with_nemo(user_input: str, rails: LLMRails) -> tuple[bool, str]:
    """
    Validates user input using NeMo Guardrails.
    Returns (is_safe: bool, response: str).
    """
    handler = NeMoOTelCallback()
    token = streaming_handler_var.set(handler)

    with tracer.start_as_current_span("guardrails.validate_input") as span:
        try:
            span.set_attribute("guardrails.framework", "nemo")
            span.set_attribute("guardrails.input_length", len(user_input))

            res = await rails.generate_async(
                messages=[{"role": "user", "content": user_input}],
                streaming_handler=handler
            )

            is_safe = True
            response_content = ""

            if res and isinstance(res, dict) and "content" in res:
                content = res["content"]
                if any(phrase in content for phrase in ["I cannot answer", "policy", "I am programmed", "I am sorry"]):
                    is_safe = False
                    response_content = content
                else:
                    is_safe = True
                    response_content = content

            elif isinstance(res, str):
                 if any(phrase in res for phrase in ["I cannot answer", "policy", "I am programmed", "I am sorry"]):
                    is_safe = False
                    response_content = res
                 else:
                    is_safe = True
                    response_content = res

            verdict = "APPROVED" if is_safe else "REJECTED"
            span.set_attribute("guardrails.outcome", "ALLOWED" if is_safe else "BLOCKED")
            span.set_attribute("risk.verdict", verdict)
            span.set_attribute("guardrails.intervened", not is_safe)

            return is_safe, response_content

        except Exception as e:
            logger.error(f"NeMo Validation Error: {e}")
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR))
            return True, ""
        finally:
            streaming_handler_var.reset(token)
