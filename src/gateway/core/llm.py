"""
Gateway Core: LLM Logic (HybridClient)
"""

import asyncio
import hashlib
import json
import logging
import os
import time

# Using google-genai for the reliable path
from google import genai
from google.genai import types
from openai import APIConnectionError, APIStatusError, AsyncOpenAI
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class HybridClient:
    def __init__(
        self,
        vllm_base_url: str = "http://vllm-service.governance-stack.svc.cluster.local:8000/v1",
        vllm_api_key: str = "EMPTY",
        vllm_model: str = "meta-llama/Llama-3.1-8B-Instruct",
        vertex_model: str = "gemini-2.5-pro",
        vertex_project: str | None = None,
        vertex_location: str = "us-central1",
        fallback_threshold_ms: float = 200.0
    ):
        """
        Initializes the HybridClient.
        """
        self.vllm_base_url = vllm_base_url
        self.vllm_api_key = vllm_api_key
        self.vllm_model = vllm_model
        self.vertex_model = vertex_model
        self.vertex_project = vertex_project or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.vertex_location = vertex_location
        self.fallback_threshold_ms = fallback_threshold_ms

        # Clients
        self.fast_client = AsyncOpenAI(
            base_url=self.vllm_base_url,
            api_key=self.vllm_api_key
        )
        # Lazy init for Vertex client
        self._vertex_client: genai.Client | None = None

    @property
    def vertex_client(self) -> genai.Client:
        if not self._vertex_client:
            self._vertex_client = genai.Client(
                vertexai=True,
                project=self.vertex_project,
                location=self.vertex_location
            )
        return self._vertex_client

    async def generate(self, prompt: str, system_instruction: str = None, mode: str = "chat", **kwargs) -> str:
        """
        Generates a response using the Hybrid Strategy.
        Attempts Fast Path (vLLM) first. Falls back to Vertex AI on Error or Latency Violation.
        """
        is_verifier = (mode == "verifier")
        stream_request = not is_verifier

        # 1. Identify FSM Mode (The "Structural Guarantee")
        fsm_mode = "none"
        fsm_constraint = "none"

        if "guided_json" in kwargs:
            fsm_mode = "json_schema"
            try:
                schema_str = json.dumps(kwargs['guided_json'], sort_keys=True)
                fsm_constraint = hashlib.md5(schema_str.encode()).hexdigest()
            except Exception:
                fsm_constraint = "hash_error"

        elif "guided_regex" in kwargs:
            fsm_mode = "regex"
            fsm_constraint = kwargs['guided_regex']

        elif "guided_choice" in kwargs:
            fsm_mode = "choice"
            fsm_constraint = str(kwargs['guided_choice'])

        with tracer.start_as_current_span("hybrid_generate") as span:
            start_time = time.time()
            span.set_attribute("gen_ai.usage.input_tokens", len(prompt) // 4)
            span.set_attribute("gen_ai.request.model", self.vllm_model)
            span.set_attribute("gen_ai.system", "hybrid")
            span.set_attribute("llm.type", "verifier" if is_verifier else "planner")

            # Log Deterministic Controls
            span.set_attribute("llm.control.temperature", kwargs.get("temperature", 0.0))
            span.set_attribute("llm.control.fsm.enabled", fsm_mode != "none")
            span.set_attribute("llm.control.fsm.mode", fsm_mode)
            span.set_attribute("llm.control.fsm.constraint", fsm_constraint)

            # 1. Try Fast Path (vLLM)
            try:
                # Calculate timeout for the first token (TTFT SLA)
                ttft_timeout = self.fallback_threshold_ms / 1000.0 * 1.1

                logger.info(f"Attempting Fast Path: {self.vllm_base_url} [Mode: {mode}, FSM: {fsm_mode}]")

                response = await self.fast_client.chat.completions.create(
                    model=self.vllm_model,
                    messages=[
                        {"role": "system", "content": system_instruction or "You are a helpful assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1024,
                    stream=stream_request,
                    **kwargs
                )

                if is_verifier:
                    # BLOCKING MODE (Verifier)
                    full_response = response.choices[0].message.content

                    end_time = time.time()
                    total_time_ms = (end_time - start_time) * 1000

                    span.set_attribute("telemetry.total_generation_time_ms", total_time_ms)
                    span.set_attribute("llm.provider", "vllm")
                    span.set_attribute("llm.mode", "fast_path_blocking")
                    span.set_attribute("telemetry.status", "success_verifier")

                    if hasattr(response, 'usage'):
                        span.set_attribute("llm.usage.completion_tokens", response.usage.completion_tokens)

                    return full_response

                else:
                    # STREAMING MODE (Planner/Chat)
                    stream = response

                    # Wait for the first chunk to validate TTFT
                    first_chunk = await asyncio.wait_for(anext(stream), timeout=ttft_timeout)

                    ttft_time = time.time()
                    ttft_ms = (ttft_time - start_time) * 1000
                    span.set_attribute("telemetry.ttft_ms", ttft_ms)
                    span.set_attribute("llm.provider", "vllm")
                    span.set_attribute("llm.mode", "fast_path_streaming")

                    if ttft_ms > self.fallback_threshold_ms:
                        logger.warning(f"Fast Path SLA Violation: {ttft_ms:.2f}ms > {self.fallback_threshold_ms}ms.")
                        raise TimeoutError("SLA Violation")

                    collected_content = []
                    token_chunks = 0

                    if first_chunk.choices[0].delta.content:
                        collected_content.append(first_chunk.choices[0].delta.content)
                        token_chunks += 1

                    async for chunk in stream:
                        if chunk.choices[0].delta.content:
                            collected_content.append(chunk.choices[0].delta.content)
                            token_chunks += 1

                    full_response = "".join(collected_content)
                    end_time = time.time()
                    total_time_ms = (end_time - start_time) * 1000

                    span.set_attribute("telemetry.total_generation_time_ms", total_time_ms)
                    span.set_attribute("gen_ai.usage.output_tokens", token_chunks)

                    num_tokens = token_chunks
                    if num_tokens > 1:
                        generation_phase_ms = (end_time - ttft_time) * 1000
                        tpot_ms = generation_phase_ms / (num_tokens - 1)
                        span.set_attribute("telemetry.tpot_ms", tpot_ms)

                    span.set_attribute("telemetry.status", "success_planner")
                    return full_response

            except (APIConnectionError, APIStatusError, asyncio.TimeoutError, StopAsyncIteration, Exception) as e:
                # 2. Fallback to Reliable Path (Vertex AI)
                elapsed = (time.time() - start_time) * 1000
                logger.warning(f"Fast Path Failed ({e!r}). Fallback to Vertex AI after {elapsed:.2f}ms")
                span.add_event("vllm_failure", attributes={"error.message": str(e), "error.type": type(e).__name__})
                span.set_attribute("telemetry.fallback_reason", str(e))

                # If this fails, it bubbles up
                return await self._call_vertex_fallback(prompt, system_instruction)

    async def _call_vertex_fallback(self, prompt: str, system_instruction: str) -> str:
        with tracer.start_as_current_span("llm.fallback.vertex") as span:
            span.set_attribute("llm.provider", "vertex_ai")
            span.set_attribute("llm.mode", "fallback")
            span.set_attribute("gen_ai.request.model", self.vertex_model)

            try:
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.7
                )
                response = await self.vertex_client.aio.models.generate_content(
                    model=self.vertex_model,
                    contents=[prompt],
                    config=config
                )
                if hasattr(response, 'usage_metadata'):
                     span.set_attribute("gen_ai.usage.output_tokens", response.usage_metadata.candidates_token_count)
                     span.set_attribute("gen_ai.usage.input_tokens", response.usage_metadata.prompt_token_count)

                return response.text
            except Exception as e:
                logger.error(f"Reliable Path also failed: {e}")
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR))
                raise e
