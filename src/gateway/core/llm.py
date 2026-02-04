"""
Gateway Core: LLM Logic (HybridClient)
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from typing import Any, Dict

from openai import APIConnectionError, APIStatusError, AsyncOpenAI
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

try:
    from google import genai
except ImportError:
    genai = None

# Import config to access the reasoning endpoint
from config.settings import Config

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class HybridClient:
    def __init__(
        self,
        vllm_base_url: str = "http://localhost:8000/v1",
        vllm_api_key: str = "EMPTY",
        vllm_model: str = "meta-llama/Llama-3.1-8B-Instruct",
        vertex_model: str = None, # Ignored in Sovereign Mode
        vertex_project: str | None = None, # Ignored
        vertex_location: str = None, # Ignored
        fallback_threshold_ms: float = 5000.0 # Relaxed timeout for local
    ):
        """
        Initializes the HybridClient (Sovereign Mode).
        Uses vLLM exclusively, routing between Fast (Control) and Reasoning endpoints.
        """
        # Fast Path Config (Control Plane)
        self.fast_base_url = vllm_base_url
        self.fast_model = vllm_model

        # Reasoning Path Config (Reasoning Plane)
        self.reasoning_base_url = Config.VLLM_REASONING_API_BASE
        self.reasoning_model = Config.MODEL_REASONING

        # Clients
        self.fast_client = AsyncOpenAI(
            base_url=self.fast_base_url,
            api_key=vllm_api_key
        )
        self.reasoning_client = AsyncOpenAI(
            base_url=self.reasoning_base_url,
            api_key=vllm_api_key
        )

        # Gemini Client
        self.gemini_client = None
        if genai:
            if Config.GOOGLE_API_KEY and Config.GOOGLE_API_KEY != "EMPTY":
                self.gemini_client = genai.Client(api_key=Config.GOOGLE_API_KEY)
            elif Config.GOOGLE_CLOUD_PROJECT and Config.GOOGLE_CLOUD_LOCATION != "local":
                self.gemini_client = genai.Client(vertexai=True, project=Config.GOOGLE_CLOUD_PROJECT, location=Config.GOOGLE_CLOUD_LOCATION)

    @property
    def vertex_client(self):
        raise NotImplementedError("Vertex AI Client is disabled in Sovereign Mode.")

    def _get_client_and_model(self, requested_model: str | None, mode: str):
        """
        Determines which backend and model to use.
        Returns: (client, base_url, effective_model)
        """
        # 1. Determine Effective Model
        effective_model = requested_model

        is_reasoning_mode = mode in ["verifier", "reasoning", "analysis"]

        if not effective_model:
            if is_reasoning_mode:
                effective_model = self.reasoning_model
            else:
                effective_model = self.fast_model

        # 2. Determine Backend Client
        if effective_model and effective_model.lower().startswith("gemini"):
            # Return Gemini client. Base URL is handled by the client lib.
            return self.gemini_client, "google_genai", effective_model

        if effective_model == self.reasoning_model or is_reasoning_mode:
             return self.reasoning_client, self.reasoning_base_url, effective_model

        return self.fast_client, self.fast_base_url, effective_model

    async def generate(self, prompt: str, system_instruction: str = None, mode: str = "chat", **kwargs) -> str:
        """
        Generates a response using the appropriate vLLM Client.
        Handles vLLM-specific Guided Generation parameters via 'extra_body'.
        """
        is_verifier = (mode == "verifier")
        stream_request = not is_verifier

        # 1. Identify FSM Mode & Prepare extra_body
        fsm_mode = "none"
        fsm_constraint = "none"
        extra_body: Dict[str, Any] = {}

        if "guided_json" in kwargs:
            fsm_mode = "json_schema"
            # Move guided_json to extra_body
            extra_body["guided_json"] = kwargs.pop("guided_json")
            try:
                schema_str = json.dumps(extra_body['guided_json'], sort_keys=True)
                fsm_constraint = hashlib.md5(schema_str.encode()).hexdigest()
            except Exception:
                fsm_constraint = "hash_error"

        elif "guided_regex" in kwargs:
            fsm_mode = "regex"
            extra_body["guided_regex"] = kwargs.pop("guided_regex")
            fsm_constraint = extra_body['guided_regex']

        elif "guided_choice" in kwargs:
            fsm_mode = "choice"
            extra_body["guided_choice"] = kwargs.pop("guided_choice")
            fsm_constraint = str(extra_body['guided_choice'])

        # 2. Select Backend & Model
        requested_model_arg = kwargs.pop("model", None)
        client, backend_url, effective_model = self._get_client_and_model(requested_model_arg, mode)

        with tracer.start_as_current_span("hybrid_generate") as span:
            start_time = time.time()
            span.set_attribute("gen_ai.usage.input_tokens", len(prompt) // 4)
            span.set_attribute("gen_ai.request.model", effective_model)
            span.set_attribute("gen_ai.system", "sovereign_vllm")
            span.set_attribute("llm.backend_url", backend_url)
            span.set_attribute("llm.type", "verifier" if is_verifier else "planner")
            span.set_attribute("llm.fsm_mode", fsm_mode)
            span.set_attribute("llm.fsm_constraint", str(fsm_constraint))

            try:
                logger.info(f"Generating via {backend_url}: [Model: {effective_model}, Mode: {mode}, FSM: {fsm_mode}]")

                # Gemini Handling
                if backend_url == "google_genai":
                    if not client:
                         raise ValueError("Gemini Client not initialized (check GOOGLE_API_KEY).")

                    from google.genai import types

                    config_args = {}
                    if system_instruction:
                        config_args["system_instruction"] = system_instruction
                    if "temperature" in kwargs:
                        config_args["temperature"] = kwargs["temperature"]
                    if "top_p" in kwargs:
                        config_args["top_p"] = kwargs["top_p"]
                    if "max_tokens" in kwargs:
                        config_args["max_output_tokens"] = kwargs["max_tokens"]
                    else:
                        config_args["max_output_tokens"] = 1024

                    if fsm_mode == "json_schema":
                         config_args["response_mime_type"] = "application/json"

                    # Execute Gemini Generation
                    response = await client.aio.models.generate_content(
                        model=effective_model,
                        contents=prompt,
                        config=types.GenerateContentConfig(**config_args)
                    )

                    full_response = response.text
                    end_time = time.time()
                    total_time_ms = (end_time - start_time) * 1000
                    span.set_attribute("telemetry.total_generation_time_ms", total_time_ms)
                    span.set_attribute("telemetry.status", "success_gemini")
                    return full_response

                # vLLM / OpenAI Handling
                # Merge extra_body if provided
                if extra_body:
                    if "extra_body" in kwargs:
                        kwargs["extra_body"].update(extra_body)
                    else:
                        kwargs["extra_body"] = extra_body

                response = await client.chat.completions.create(
                    model=effective_model,
                    messages=[
                        {"role": "system", "content": system_instruction or "You are a helpful assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1024,
                    stream=stream_request,
                    **kwargs
                )

                if is_verifier:
                    # BLOCKING MODE
                    full_response = response.choices[0].message.content
                    end_time = time.time()
                    total_time_ms = (end_time - start_time) * 1000
                    span.set_attribute("telemetry.total_generation_time_ms", total_time_ms)
                    span.set_attribute("telemetry.status", "success_verifier")
                    if hasattr(response, 'usage'):
                         span.set_attribute("llm.usage.completion_tokens", response.usage.completion_tokens)
                    return full_response

                else:
                    # STREAMING MODE
                    stream = response
                    collected_content = []
                    async for chunk in stream:
                        if chunk.choices[0].delta.content:
                            collected_content.append(chunk.choices[0].delta.content)
                    full_response = "".join(collected_content)
                    end_time = time.time()
                    total_time_ms = (end_time - start_time) * 1000
                    span.set_attribute("telemetry.total_generation_time_ms", total_time_ms)
                    span.set_attribute("telemetry.status", "success_planner")
                    return full_response

            except (APIConnectionError, APIStatusError, Exception) as e:
                elapsed = (time.time() - start_time) * 1000
                logger.error(f"Generation Failed on {backend_url} ({e!r}).")
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR))
                raise e
