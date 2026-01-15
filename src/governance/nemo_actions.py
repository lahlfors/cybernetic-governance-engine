import logging
from typing import Dict, Any, List, Optional
from src.governance.safety import safety_filter

logger = logging.getLogger("NeMo.Actions")

# Mock latency check for SC-2
def _check_latency_ms() -> float:
    # In a real system, this would measure actual inference latency.
    return 100.0  # Simulated low latency

def check_approval_token(context: Dict[str, Any] = {}, event: Dict[str, Any] = {}) -> bool:
    """
    NeMo Action: SC-1 Authorization Check.
    Checks if a valid approval token exists for write operations.

    In NeMo, returning False from an action called in a guardrail flow
    can trigger a blocking response if configured.
    """
    logger.info("🛡️ NeMo Action: check_approval_token invoked.")

    # Extract token from context variables
    token = context.get("approval_token")

    if not token:
        logger.warning("⛔ SC-1 Violation: No approval token found.")
        return False

    # Mock validation logic
    if token == "valid_token":
        logger.info("✅ SC-1 Passed: Token valid.")
        return True
    else:
        logger.warning("⛔ SC-1 Violation: Invalid token.")
        return False

def check_latency(context: Dict[str, Any] = {}, event: Dict[str, Any] = {}) -> bool:
    """
    NeMo Action: SC-2 Latency Check.
    Blocks tool call if latency > 200ms.
    """
    latency = _check_latency_ms()
    logger.info(f"🛡️ NeMo Action: check_latency invoked. Latency: {latency}ms")

    if latency > 200:
        logger.warning(f"⛔ SC-2 Violation: High latency ({latency}ms).")
        return False

    return True
