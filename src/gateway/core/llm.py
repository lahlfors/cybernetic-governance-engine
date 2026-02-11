"""
Gateway Core: LLM Logic (GatewayClient)
Sovereign Execution Engine (vLLM Only)
"""

import logging
import time
from typing import Any

from openai import AsyncOpenAI
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from config.settings import Config

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class GatewayClient:
    def __init__(self):
        """
        Initializes the GatewayClient (Sovereign Mode).
        Directly controls the two vLLM nodes: Reasoning (Brain) and Governance (Police).
        """
        # Node A: The Brain (Reasoning/Planner)
        self.reasoning_client = AsyncOpenAI(
            base_url=Config.VLLM_REASONING_API_BASE,
            api_key="EMPTY"
        )
        self.reasoning_model = Config.MODEL_REASONING

        # Node B: The Police (Governance/FSM)
        self.governance_client = AsyncOpenAI(
            base_url=Config.VLLM_FAST_API_BASE,
            api_key="EMPTY"
        )
        self.governance_model = Config.MODEL_FAST

    def _get_route(self, mode: str) -> tuple[AsyncOpenAI, str]:
        """
        Routes the request to the appropriate vLLM node based on the mode.
        """
        # Modes that require deep thought or planning go to the Reasoning Node
        if mode in ["planner", "reasoning", "analysis"]:
            return self.reasoning_client, self.reasoning_model

        # Modes that require strict FSM adherence or fast checks go to the Governance Node
        # e.g., "verifier", "chat", "json_schema"
        return self.governance_client, self.governance_model

    async def generate(self, prompt: str, system_instruction: str = None, mode: str = "chat", **kwargs) -> str:
        """
        Generates a response using the appropriate vLLM Client.
        Handles vLLM-specific Guided Generation parameters via 'extra_body'.
        """
        client, model = self._get_route(mode)

        # Prepare vLLM-specific parameters (extra_body)
        extra_body: dict[str, Any] = {}

        # Handle Guided Decoding (FSM)
        # OpenAI "Structured Outputs" style is supported by vLLM via `guided_json`, `guided_regex`, etc.
        # We map our internal kwargs to vLLM's `extra_body`.

        if "guided_json" in kwargs:
            extra_body["guided_json"] = kwargs.pop("guided_json")
        elif "guided_regex" in kwargs:
            extra_body["guided_regex"] = kwargs.pop("guided_regex")
        elif "guided_choice" in kwargs:
            extra_body["guided_choice"] = kwargs.pop("guided_choice")

        # Merge any existing extra_body
        if "extra_body" in kwargs:
            extra_body.update(kwargs.pop("extra_body"))

        # Default parameters
        temperature = kwargs.pop("temperature", 0.0)
        max_tokens = kwargs.pop("max_tokens", 1024)

        # If user provided a specific model arg, ignore it in favor of the routed model
        # (Sovereign Enforcement), or allow override if debugging?
        # We stick to the routed model for strictness, unless we want to support dynamic model selection.
        # The prompt implies strict routing: "Refactoring Master Plan... Sovereign Defaults".
        # We will use the routed model.

        with tracer.start_as_current_span("gateway.generate") as span:
            start_time = time.time()
            span.set_attribute("gen_ai.system", "sovereign_vllm")
            span.set_attribute("gen_ai.request.model", model)
            span.set_attribute("llm.mode", mode)
            span.set_attribute("llm.base_url", str(client.base_url))

            try:
                logger.info(f"Generating via {client.base_url} [Model: {model}, Mode: {mode}]")

                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": prompt})

                # Determine if we stream or block.
                # The original HybridClient treated "verifier" as blocking, others as streaming?
                # Actually, `src/gateway/server/main.py` seems to yield the full response as one chunk anyway:
                # `full_response = await self.llm_client.generate(...)`
                # `yield gateway_pb2.ChatResponse(content=full_response, is_final=True)`
                # So we can just block and return the full string for simplicity here.
                # If streaming is needed, we can implement it.
                # The prompt example code was `requests.post`, implying simple request/response.

                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    extra_body=extra_body if extra_body else None,
                    **kwargs
                )

                content = response.choices[0].message.content

                end_time = time.time()
                span.set_attribute("telemetry.generation_ms", (end_time - start_time) * 1000)

                return content

            except Exception as e:
                logger.error(f"Generation Failed: {e}")
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR))
                raise e
