import logging
from opentelemetry import trace
from typing import Optional, Any

# We need to import the correct types from ADK
# Using try-except block to handle potential import locations depending on ADK version
try:
    from google.adk.agents.callback_context import CallbackContext
    from google.adk.models import LlmResponse
except ImportError:
    # Fallback or mock for runtime if adk structure differs slightly in this environment
    # But for type hinting we can use Any
    CallbackContext = Any
    LlmResponse = Any

logger = logging.getLogger("OTelInterceptor")

def otel_interceptor_callback(
    callback_context: CallbackContext,
    llm_response: LlmResponse
) -> Optional[LlmResponse]:
    """
    Standard ADK AfterModelCallback signature.
    Intercepts the ADK response to add OTel attributes.
    """
    span = trace.get_current_span()
    if not span or not span.is_recording():
        return None

    try:
        # Inject OTel attributes
        # callback_context has agent_name, invocation_id etc.
        if hasattr(callback_context, 'agent_name'):
            span.set_attribute("gen_ai.agent.name", callback_context.agent_name)
        if hasattr(callback_context, 'invocation_id'):
            span.set_attribute("gen_ai.invocation_id", callback_context.invocation_id)

        # Capture text content
        if hasattr(llm_response, 'text') and llm_response.text:
            span.set_attribute("gen_ai.content.completion", str(llm_response.text)[:1000])

        # Capture Metadata (Gemini Specifics)
        # Capture usage data if available in the LlmResponse
        if hasattr(llm_response, 'usage_metadata'):
             # Check specific attributes of usage_metadata
             if hasattr(llm_response.usage_metadata, 'prompt_token_count'):
                span.set_attribute("gen_ai.usage.prompt_tokens", llm_response.usage_metadata.prompt_token_count)
             if hasattr(llm_response.usage_metadata, 'candidates_token_count'):
                span.set_attribute("gen_ai.usage.completion_tokens", llm_response.usage_metadata.candidates_token_count)

        # Check for safety ratings if available
        if hasattr(llm_response, 'safety_ratings'):
             span.set_attribute("gen_ai.safety.ratings", str(llm_response.safety_ratings))

        logger.info(f"✅ OTel Interceptor: Enriched span for agent {getattr(callback_context, 'agent_name', 'unknown')}")

    except Exception as e:
        logger.warning(f"⚠️ OTel Interceptor Failed: {e}")

    # Return None to allow the ADK to proceed with the original response
    return None
