"""
Gateway Core: LLM Logic (HybridClient)
Refactored to use Google Gen AI SDK exclusively (removing vLLM).
"""

import asyncio
import hashlib
import json
import logging
import os
import time

from google import genai
from google.genai import types
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

# Import settings to get default models
try:
    from config.settings import MODEL_FAST, MODEL_REASONING
except ImportError:
    # Fallback if config not found (e.g. running in isolation)
    MODEL_FAST = os.getenv("MODEL_FAST", "gemini-2.5-flash-lite")
    MODEL_REASONING = os.getenv("MODEL_REASONING", "gemini-2.5-pro")

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class HybridClient:
    def __init__(
        self,
        model_fast: str = MODEL_FAST,
        model_reasoning: str = MODEL_REASONING,
        project: str | None = None,
        location: str = "us-central1",
    ):
        """
        Initializes the HybridClient.
        Now exclusively uses Google Gen AI SDK.

        Args:
            model_fast: The model to use for the 'Fast Path' (default: Gemini Flash Lite).
            model_reasoning: The model to use for the 'Reasoning/Fallback Path' (default: Gemini Pro).
            project: GCP Project ID.
            location: GCP Region.
        """
        self.model_fast = model_fast
        self.model_reasoning = model_reasoning
        self.project = project or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = location

        # Lazy init for Gen AI client
        self._client: genai.Client | None = None

    @property
    def client(self) -> genai.Client:
        if not self._client:
            self._client = genai.Client(
                vertexai=True,
                project=self.project,
                location=self.location
            )
        return self._client

    async def generate(self, prompt: str, system_instruction: str = None, mode: str = "chat", **kwargs) -> str:
        """
        Generates a response using the configured Gemini models.

        Args:
            prompt: The user prompt.
            system_instruction: System prompt/instruction.
            mode: 'chat', 'planner', or 'verifier'.
            **kwargs: Additional generation config (temperature, guided_json, etc).
        """
        is_verifier = (mode == "verifier")

        # Determine Model: Verifier uses Reasoning Model, others use Fast Model
        # (Or strict adherence to 'Fast Path' replacement implies Fast Model for standard flow)
        # We'll stick to using model_fast for the primary "Fast Path" replacement.
        # If the user wants specific reasoning, they might need to specify it, but for now we default to Fast.
        # However, purely for safety, if mode is 'verifier', using the reasoning model is usually better.
        # Let's use model_fast for everything as requested ("replacing the AsyncOpenAI vLLM client" which was the fast path).
        target_model = self.model_fast

        # Handle Guided JSON (JSON Mode)
        response_mime_type = "text/plain"
        response_schema = None

        fsm_mode = "none"
        fsm_constraint = "none"

        if "guided_json" in kwargs:
            fsm_mode = "json_schema"
            response_mime_type = "application/json"
            response_schema = kwargs.pop("guided_json") # Remove from kwargs to avoid conflict if passed elsewhere

            # Create hash for telemetry
            try:
                schema_str = json.dumps(response_schema, sort_keys=True)
                fsm_constraint = hashlib.md5(schema_str.encode()).hexdigest()
            except Exception:
                fsm_constraint = "hash_error"

        elif "guided_regex" in kwargs:
             # Gemini doesn't support regex constraints natively in the same way vLLM does yet via SDK (maybe via controlled generation?)
             # For now, we ignore or log.
             # To stay compliant with the request "ensure... guided_json mechanism works", we focus on JSON.
             fsm_mode = "regex (unsupported on Vertex)"
             kwargs.pop("guided_regex")

        elif "guided_choice" in kwargs:
             # Enum constraint
             fsm_mode = "choice (unsupported on Vertex)"
             kwargs.pop("guided_choice")

        with tracer.start_as_current_span("hybrid_generate") as span:
            start_time = time.time()
            span.set_attribute("gen_ai.request.model", target_model)
            span.set_attribute("gen_ai.system", "vertex_ai")
            span.set_attribute("llm.type", mode)
            span.set_attribute("llm.control.fsm.mode", fsm_mode)
            span.set_attribute("llm.control.fsm.constraint", fsm_constraint)

            try:
                # Build Config
                # Map standard kwargs to GenerateContentConfig
                temperature = kwargs.get("temperature", 0.0)

                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=temperature,
                    response_mime_type=response_mime_type,
                    response_schema=response_schema
                )

                logger.info(f"Generating with {target_model} [Mode: {mode}, JSON: {fsm_mode}]")

                response = await self.client.aio.models.generate_content(
                    model=target_model,
                    contents=[prompt],
                    config=config
                )

                end_time = time.time()
                total_time_ms = (end_time - start_time) * 1000

                span.set_attribute("telemetry.total_generation_time_ms", total_time_ms)
                span.set_attribute("telemetry.status", "success")

                if hasattr(response, 'usage_metadata'):
                     span.set_attribute("gen_ai.usage.output_tokens", response.usage_metadata.candidates_token_count)
                     span.set_attribute("gen_ai.usage.input_tokens", response.usage_metadata.prompt_token_count)

                return response.text

            except Exception as e:
                logger.error(f"Generation Failed: {e}")
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR))
                raise e
