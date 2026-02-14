"""
Factory for creating NeMo Guardrails manager with vLLM/Llama support.
Moved to src/gateway/governance/nemo/manager.py
"""
import logging
import os
from typing import Any, List, Optional, AsyncIterator

import nest_asyncio
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessageChunk, AIMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult, ChatGeneration
from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.context import streaming_handler_var
from nemoguardrails.llm.providers import register_llm_provider
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from src.gateway.governance.nemo.exporter import NeMoOTelCallback

# Configure Logging
logger = logging.getLogger("Gateway.NeMoManager")
tracer = trace.get_tracer("gateway.governance.nemo")

class VLLMLLM(BaseChatModel):
    """Custom LangChain-compatible wrapper for vLLM using LiteLLM."""

    model_name: str = os.getenv("GUARDRAILS_MODEL_NAME", "meta-llama/Meta-Llama-3.1-8B-Instruct")
    api_base: str = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
    api_key: str = os.getenv("VLLM_API_KEY", "EMPTY")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Re-fetch env vars to be safe if they changed or were set after import
        self.model_name = os.getenv("GUARDRAILS_MODEL_NAME", self.model_name)
        self.api_base = os.getenv("VLLM_BASE_URL", self.api_base)
        self.api_key = os.getenv("VLLM_API_KEY", self.api_key)
        print(f"DEBUG: VLLMLLM initialized with model={self.model_name}, base={self.api_base}")

    @property
    def _llm_type(self) -> str:
        return "vllm"

    def _generate(self, messages: List[BaseMessage], stop: list[str] | None = None, run_manager: Any = None, **kwargs: Any) -> ChatResult:
        """Call the vLLM model via LiteLLM."""
        try:
            import litellm
            
            # Ensure model has openai/ prefix if needed by litellm for generic vLLM
            model_id = self.model_name
            if not model_id.startswith("openai/") and "gpt" not in model_id:
                model_id = f"openai/{model_id}"

            print(f"DEBUG: Calling vLLM via litellm... model={model_id} base={self.api_base}")
            
            # Format messages for litellm
            formatted_messages = [{"role": m.type if m.type != "ai" else "assistant", "content": m.content} for m in messages]
            # Map 'human' to 'user' if needed
            for m in formatted_messages:
                if m["role"] == "human": m["role"] = "user"

            response = litellm.completion(
                model=model_id,
                api_base=self.api_base,
                api_key=self.api_key,
                messages=formatted_messages,
                stop=stop,
                **kwargs
            )

            content = response.choices[0].message.content
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

        except Exception as e:
            logger.error(f"Failed to call vLLM: {e}")
            raise e

    async def _acall(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, run_manager: Any = None, **kwargs: Any) -> str:
        """NeMo 0.10.0+ Compat: Wraps _agenerate to return string."""
        if not messages:
            return ""
            
        result = await self._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
        return result.generations[0].message.content

    async def _agenerate(self, messages: List[BaseMessage], stop: list[str] | None = None, run_manager: Any = None, **kwargs: Any) -> ChatResult:
        """Async call to the vLLM model via LiteLLM."""
        try:
            import litellm
            
            model_id = self.model_name
            if not model_id.startswith("openai/") and "gpt" not in model_id:
                model_id = f"openai/{model_id}"

            print(f"DEBUG: Async Calling vLLM via litellm... model={model_id} base={self.api_base}")
            
            formatted_messages = [{"role": m.type if m.type != "ai" else "assistant", "content": m.content} for m in messages]
            for m in formatted_messages:
                if m["role"] == "human": m["role"] = "user"

            response = await litellm.acompletion(
                model=model_id,
                api_base=self.api_base,
                api_key=self.api_key,
                messages=formatted_messages,
                stop=stop,
                **kwargs
            )
            content = response.choices[0].message.content
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])
        except Exception as e:
            logger.error(f"Failed to call vLLM (async): {e}")
            raise e

    async def _astream(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, run_manager: Any = None, **kwargs: Any) -> AsyncIterator[ChatGenerationChunk]:
        """
        Enables Optimistic Streaming for NeMo Guardrails.
        """
        import litellm

        model_id = self.model_name
        if not model_id.startswith("openai/") and "gpt" not in model_id:
            model_id = f"openai/{model_id}"

        formatted_messages = [{"role": m.type if m.type != "ai" else "assistant", "content": m.content} for m in messages]
        for m in formatted_messages:
            if m["role"] == "human": m["role"] = "user"

        # Use litellm with stream=True
        stream = await litellm.acompletion(
            model=model_id,
            messages=formatted_messages,
            api_base=self.api_base,
            api_key=self.api_key,
            stream=True,
            stop=stop,
            **kwargs
        )

        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                # Yield it as a LangChain Chunk for NeMo
                yield ChatGenerationChunk(message=AIMessageChunk(content=content))
                # Optional: Notify callbacks
                if run_manager:
                    await run_manager.on_llm_new_token(content)

    @property
    def _identifying_params(self) -> dict:
        return {"model": self.model_name, "api_base": self.api_base}


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
        from src.gateway.governance.nemo.actions import (
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
