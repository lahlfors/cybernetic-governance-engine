"""
HybridClient: Implements the "Fast Path" (vLLM) vs. "Reliable Path" (Vertex AI) routing logic.
Treats latency as a currency: 'buys' reliability if the fast path is too slow.
"""

import time
import asyncio
import logging
import os
from typing import AsyncGenerator, Any, Optional

from openai import AsyncOpenAI, APIConnectionError, APIStatusError
from opentelemetry import trace
# Using google-genai for the reliable path
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class HybridClient:
    def __init__(
        self,
        vllm_base_url: str = "http://vllm-service.governance-stack.svc.cluster.local:8000/v1",
        vllm_api_key: str = "EMPTY",
        vllm_model: str = "google/gemma-3-27b-it",
        vertex_model: str = "gemini-1.5-pro-001",
        vertex_project: Optional[str] = None,
        vertex_location: str = "us-central1",
        fallback_threshold_ms: float = 200.0
    ):
        """
        Initializes the HybridClient.

        Args:
            vllm_base_url: The internal cluster URL for the vLLM service.
            vllm_api_key: API key for vLLM (usually EMPTY for internal).
            vllm_model: Model name to request from vLLM.
            vertex_model: Fallback model on Vertex AI.
            vertex_project: GCP Project ID.
            vertex_location: GCP Region.
            fallback_threshold_ms: Latency threshold (TTFT) in ms to trigger fallback.
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
        # Lazy init for Vertex client to avoid authenticating if not needed immediately
        self._vertex_client: Optional[genai.Client] = None

    @property
    def vertex_client(self) -> genai.Client:
        if not self._vertex_client:
            self._vertex_client = genai.Client(
                vertexai=True,
                project=self.vertex_project,
                location=self.vertex_location
            )
        return self._vertex_client

    async def generate(self, prompt: str, system_instruction: str = None) -> str:
        """
        Generates a response using the Hybrid Strategy.
        Attempts Fast Path (vLLM) first. Falls back to Vertex AI on Error or Latency Violation.

        Uses streaming to accurately measure Time-To-First-Token (TTFT).
        """
        with tracer.start_as_current_span("hybrid_generate") as span:
            start_time = time.time()
            span.set_attribute("prompt_length", len(prompt))

            # 1. Try Fast Path (vLLM)
            try:
                # Calculate timeout for the first token (TTFT SLA)
                # We give a small buffer (e.g. 10%) for network RTT vs server processing
                ttft_timeout = self.fallback_threshold_ms / 1000.0 * 1.1

                logger.info(f"Attempting Fast Path: {self.vllm_base_url}")

                # Initiate stream
                stream = await self.fast_client.chat.completions.create(
                    model=self.vllm_model,
                    messages=[
                        {"role": "system", "content": system_instruction or "You are a helpful assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1024,
                    stream=True
                )

                # Wait for the first chunk to validate TTFT
                # We use anext() to get the first item from the async iterator
                first_chunk = await asyncio.wait_for(anext(stream), timeout=ttft_timeout)

                ttft_ms = (time.time() - start_time) * 1000
                span.set_attribute("telemetry.ttft_ms", ttft_ms)
                span.set_attribute("telemetry.provider", "vllm")

                # Check strict SLA (though wait_for handles the timeout)
                if ttft_ms > self.fallback_threshold_ms:
                    logger.warning(f"Fast Path SLA Violation (measured): {ttft_ms:.2f}ms > {self.fallback_threshold_ms}ms. Triggering Fallback.")
                    raise TimeoutError("SLA Violation")

                # Accumulate the response
                collected_content = []

                # Add first chunk content
                if first_chunk.choices[0].delta.content:
                    collected_content.append(first_chunk.choices[0].delta.content)

                # Consume the rest of the stream normally
                async for chunk in stream:
                    if chunk.choices[0].delta.content:
                        collected_content.append(chunk.choices[0].delta.content)

                full_response = "".join(collected_content)
                span.set_attribute("telemetry.status", "success_fast_path")
                return full_response

            except (APIConnectionError, APIStatusError, asyncio.TimeoutError, StopAsyncIteration, Exception) as e:
                # 2. Fallback to Reliable Path (Vertex AI)
                elapsed = (time.time() - start_time) * 1000
                logger.warning(f"Fast Path Failed (Error or Latency: {e!r}). Fallback to Vertex AI after {elapsed:.2f}ms")
                span.set_attribute("telemetry.fallback_reason", str(e))
                span.set_attribute("telemetry.provider", "vertex_ai")

                return await self._call_vertex_fallback(prompt, system_instruction)

    async def _call_vertex_fallback(self, prompt: str, system_instruction: str) -> str:
        """Executes the request against Vertex AI."""
        try:
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7
            )

            # Using the google-genai async method
            response = await self.vertex_client.aio.models.generate_content(
                model=self.vertex_model,
                contents=[prompt],
                config=config
            )

            return response.text
        except Exception as e:
            logger.error(f"Reliable Path also failed: {e}")
            raise e
