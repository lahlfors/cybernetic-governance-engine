import logging
from typing import Any

try:
    from nemoguardrails.streaming import StreamingHandler
except ImportError:
    # Fallback for environments where NeMo is not installed (e.g. Agent)
    StreamingHandler = object
from opentelemetry import trace

logger = logging.getLogger("NeMoOTelExporter")
tracer = trace.get_tracer("src.governance.nemo")

class NeMoOTelCallback(StreamingHandler):
    """
    ISO 42001 Compliance Exporter for NeMo Guardrails.

    Hooks into the NeMo event loop to create OpenTelemetry spans for every
    guardrail intervention, satisfying Annex A.6.2.8 (Event Logging).
    """

    def __init__(self):
        super().__init__()
        self.current_span = None

    async def on_action_start(self, action: str, **kwargs: Any):
        """
        Called when a guardrail action starts.
        We start a span to track the execution of this specific control.
        """
        # We focus on "check" actions which usually imply a guardrail
        # e.g., 'self_check_input', 'detect_jailbreak', 'check_hallucination'
        if "check" in action or "guard" in action or "detect" in action:
            self.current_span = tracer.start_span(f"guardrail.intervention.{action}")
            self.current_span.set_attribute("guardrail.id", action)
            self.current_span.set_attribute("iso.control_id", "A.6.2.8") # Event Logging
            self.current_span.set_attribute("iso.requirement", "Transparency of AI Systems")
            logger.info(f"🛡️ Guardrail Started: {action} (ISO A.6.2.8)")

    async def on_action_end(self, action: str, result: Any = None, **kwargs: Any):
        """
        Called when a guardrail action finishes.
        We record the outcome (Allowed/Blocked) and close the span.
        """
        if self.current_span:
            outcome = "ALLOWED"

            # Heuristic: If the result is explicitly False (often used in boolean rails)
            # or if the result contains specific "block" signals.
            # NeMo actions return varied types, so we need to be defensive.
            if result is False:
                outcome = "BLOCKED"
            elif isinstance(result, dict) and result.get("status") == "blocked":
                outcome = "BLOCKED"

            self.current_span.set_attribute("guardrail.outcome", outcome)

            if outcome == "BLOCKED":
                self.current_span.set_attribute("guardrail.block_reason", str(result))
                logger.warning(f"⛔ Guardrail BLOCKED: {action} | Result: {result}")
            else:
                logger.info(f"✅ Guardrail PASSED: {action}")

            self.current_span.end()
            self.current_span = None
