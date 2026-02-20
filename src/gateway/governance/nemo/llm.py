
import logging
import json
from typing import Any, List, Optional, AsyncIterator
import os

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessageChunk, AIMessage, HumanMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult, ChatGeneration

from src.governed_financial_advisor.infrastructure.config_manager import config_manager

# Configure Logging
logger = logging.getLogger("NeMo.LLM")

class VLLMLLM(BaseChatModel):
    """Custom LangChain-compatible wrapper for vLLM using LiteLLM."""

    model_name: str = config_manager.get("GUARDRAILS_MODEL_NAME", "meta-llama/Meta-Llama-3.1-8B-Instruct")
    api_base: str = config_manager.get("VLLM_BASE_URL", "http://localhost:8000/v1")
    api_key: str = config_manager.get("VLLM_API_KEY", "EMPTY")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.info(f"DEBUG: VLLMLLM initialized with model={self.model_name}, base={self.api_base}")

    @property
    def _llm_type(self) -> str:
        return "vllm"

    def _generate(self, messages: List[BaseMessage], stop: list[str] | None = None, run_manager: Any = None, **kwargs: Any) -> ChatResult:
        """Call the vLLM model via LiteLLM."""
        try:
            import litellm
            
            # Enable generic vLLM support via OpenAI protocol
            # We use custom_llm_provider="openai" instead of prefixing model_name 
            # to avoid sending "openai/" prefix to the vLLM server (which causes 404).
            model_id = self.model_name
            
            # Dynamic Routing Logic
            api_base = self.api_base
            if "deepseek" in model_id.lower() or "reasoning" in model_id.lower():
                reasoning_base = config_manager.get("VLLM_REASONING_API_BASE")
                if reasoning_base:
                    api_base = reasoning_base
                    print(f"DEBUG: Routing to Reasoning Service: {api_base}")
            else:
                 fast_base = config_manager.get("VLLM_FAST_API_BASE")
                 if fast_base:
                     api_base = fast_base
                     print(f"DEBUG: Routing to Fast/Governance Service: {api_base}")

            print(f"DEBUG: Calling vLLM via litellm... model={model_id} base={api_base}")
            
            # Format messages for litellm
            formatted_messages = [{"role": m.type if m.type != "ai" else "assistant", "content": m.content} for m in messages]
            # Map 'human' to 'user' if needed, though 'user' is standard. BaseMessage usually has 'human', 'ai', 'system'.
            for m in formatted_messages:
                if m["role"] == "human": m["role"] = "user"

            response = litellm.completion(
                model=model_id,
                custom_llm_provider="openai",
                api_base=api_base,
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
            
            model_id = self.model_name.replace("openai/", "")

            # Dynamic Routing Logic (Async)
            api_base = self.api_base
            if "deepseek" in model_id.lower() or "reasoning" in model_id.lower():
                reasoning_base = config_manager.get("VLLM_REASONING_API_BASE")
                if reasoning_base:
                    api_base = reasoning_base
                    logger.info(f"DEBUG: Routing to Reasoning Service: {api_base}")
            else:
                 fast_base = config_manager.get("VLLM_FAST_API_BASE")
                 if fast_base:
                     api_base = fast_base
                     logger.info(f"DEBUG: Routing to Fast/Governance Service: {api_base}")

            logger.info(f"DEBUG: Async Calling vLLM via litellm... model={model_id} base={api_base}")
            logger.info(f"DEBUG: vLLM Request Messages: {json.dumps([{'role': m.type if m.type != 'ai' else 'assistant', 'content': m.content} for m in messages])}")
            
            formatted_messages = [{"role": m.type if m.type != "ai" else "assistant", "content": m.content} for m in messages]
            for m in formatted_messages:
                if m["role"] == "human": m["role"] = "user"

            try:
                response = await litellm.acompletion(
                    model=model_id,
                    custom_llm_provider="openai",
                    api_base=api_base,
                    api_key=self.api_key,
                    messages=formatted_messages,
                    stop=stop,
                    **kwargs
                )
                content = response.choices[0].message.content
                logger.info(f"DEBUG: vLLM Response Content: {content[:100]}...")
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])
            except Exception as e:
                logger.error(f"❌ Failed to call vLLM (async): {e}")
                raise e
        except Exception as e:
            logger.error(f"❌ Failed to initialize/call vLLM: {e}")
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
