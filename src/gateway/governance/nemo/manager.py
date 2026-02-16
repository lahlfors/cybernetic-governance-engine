import logging
import os
import sys
from typing import Any, Optional

from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.context import streaming_handler_var
from opentelemetry import trace

# Import Actions so they register
import src.gateway.governance.nemo.actions as actions

# Configure Logging
logger = logging.getLogger("NeMo.Manager")
tracer = trace.get_tracer("gateway.governance.nemo")

# OTel Callback (Inline Definition or Import)
try:
    from nemoguardrails.streaming import StreamingHandler
except ImportError:
    StreamingHandler = object

class NeMoOTelCallback(StreamingHandler):
    """
    ISO 42001 Compliance Exporter for NeMo Guardrails.
    """
    def __init__(self):
        super().__init__()
        self.current_span = None

    async def on_action_start(self, action: str, **kwargs: Any):
        if "check" in action or "guard" in action or "detect" in action:
            self.current_span = tracer.start_span(f"guardrail.intervention.{action}")
            self.current_span.set_attribute("guardrail.id", action)
            self.current_span.set_attribute("iso.control_id", "A.6.2.8")
            logger.info(f"🛡️ Guardrail Started: {action}")

    async def on_action_end(self, action: str, result: Any = None, **kwargs: Any):
        if self.current_span:
            outcome = "ALLOWED"
            if result is False:
                outcome = "BLOCKED"
            elif isinstance(result, dict) and result.get("status") == "blocked":
                outcome = "BLOCKED"

            self.current_span.set_attribute("guardrail.outcome", outcome)
            if outcome == "BLOCKED":
                logger.warning(f"⛔ Guardrail BLOCKED: {action} | Result: {result}")

            self.current_span.end()
            self.current_span = None

class NeMoManager:
    """
    Manages the lifecycle and execution of NeMo Guardrails within the Gateway.
    """

    def __init__(self):
        self.rails: Optional[LLMRails] = None
        self.config_path = os.path.join(os.path.dirname(__file__), "config")
        self._load_rails()

    def _load_rails(self):
        """Initializes NeMo Rails from the config directory."""
        if not os.path.exists(self.config_path):
            logger.error(f"❌ Rails config not found at {self.config_path}")
            return

        try:
            logger.info(f"🔄 Loading NeMo Guardrails from {self.config_path}...")
            config = RailsConfig.from_path(self.config_path)
            self.rails = LLMRails(config)
            logger.info("✅ NeMo Guardrails loaded successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to load NeMo Guardrails: {e}")
            self.rails = None

    async def check_guardrails(self, input_text: str, context: Optional[dict] = None) -> dict:
        """
        Checks input against NeMo Guardrails.
        Returns a dict with 'response' (the possibly modified text) and 'blocked' status.

        PRODUCTION SAFETY: Fails Closed.
        If rails are not initialized or an error occurs, the request is BLOCKED.
        """
        if not self.rails:
            logger.critical("NeMo Rails not initialized. FAILING CLOSED.")
            return {
                "response": "Safety System Unavailable. Request Blocked.",
                "blocked": True,
                "error": "Guardrails Not Initialized"
            }

        # OTel Context
        handler = NeMoOTelCallback()
        token = streaming_handler_var.set(handler)

        try:
            response = await self.rails.generate_async(
                messages=[{"role": "user", "content": input_text}],
                streaming_handler=handler
            )

            content = ""
            if response and response.response:
                content = response.response[0]["content"]

            # Heuristic for blocked content
            # If NeMo returns a refusal message defined in Colang (e.g., "I cannot answer that"),
            # we might consider it blocked.
            # Ideally, NeMo response object would have metadata, but generate_async returns a simplified object.

            return {
                "response": content,
                "blocked": False # Basic return for now
            }

        except Exception as e:
            logger.error(f"Guardrail execution failed: {e}")
            # FAIL CLOSED: Any error in safety check MUST result in a block.
            return {
                "response": "Internal Governance Error. Request Blocked.",
                "blocked": True,
                "error": str(e)
            }
        finally:
            streaming_handler_var.reset(token)
