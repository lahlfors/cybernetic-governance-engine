import logging
from opentelemetry import trace
from typing import Any

logger = logging.getLogger("OTelInterceptor")

def otel_interceptor_callback(agent: Any, request: Any, response: Any):
    """
    Intercepts the ADK response to add OTel attributes.
    Captures safety ratings and reasoning content if available.
    """
    span = trace.get_current_span()
    if not span or not span.is_recording():
        return response

    try:
        # Standard attributes
        span.set_attribute("gen_ai.agent.name", agent.name)

        # Capture text content
        # ADK response objects usually have a 'text' attribute
        if hasattr(response, 'text') and response.text:
            # Truncate for safety/size
            span.set_attribute("gen_ai.content.completion", str(response.text)[:1000])

        # Capture Metadata (Gemini Specifics)
        # We need to inspect the underlying generation object if accessible.
        # In ADK, response might wrap the underlying model response.
        # We look for 'raw_response', 'metadata', or similar.

        # Example: Safety Ratings
        # This depends on the exact structure of the ADK response object.
        # We try to access common patterns.
        if hasattr(response, 'safety_ratings'):
             span.set_attribute("gen_ai.safety.ratings", str(response.safety_ratings))

        # Example: Usage
        if hasattr(response, 'usage_metadata'):
             span.set_attribute("gen_ai.usage.prompt_tokens", response.usage_metadata.prompt_token_count)
             span.set_attribute("gen_ai.usage.completion_tokens", response.usage_metadata.candidates_token_count)

        logger.info(f"✅ OTel Interceptor: Enriched span for agent {agent.name}")

    except Exception as e:
        logger.warning(f"⚠️ OTel Interceptor Failed: {e}")

    return response
