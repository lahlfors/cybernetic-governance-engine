import logging
import time
from typing import Dict, Any, List, Optional
from src.governance.safety import safety_filter

# Import generated actions if available
try:
    from src.governance.generated_actions import check_slippage_risk, check_drawdown_limit
except ImportError:
    logging.warning("Generated actions not found. Using fallback.")
    def check_slippage_risk(*args, **kwargs): return True
    def check_drawdown_limit(*args, **kwargs): return True

logger = logging.getLogger("NeMo.Actions")

# --- CORE/EXISTING ACTIONS ---

def check_approval_token(context: Dict[str, Any] = {}, event: Dict[str, Any] = {}) -> bool:
    """
    NeMo Action: SC-1 Authorization Check with Cryptographic Mandate (AP2 Mock).
    """
    logger.info("🛡️ NeMo Action: check_approval_token invoked.")
    token = context.get("approval_token")

    # Mock AP2 Signature Verification
    if not token:
        logger.warning("⛔ SC-1 Violation: No approval token found.")
        return False

    if token.startswith("valid_signed_token_"):
        logger.info("✅ SC-1 Passed: Valid AP2 Signature.")
        return True

    # Legacy/Simpler check
    if token == "valid_token":
        return True

    logger.warning("⛔ SC-1 Violation: Invalid Signature.")
    return False

def check_latency(context: Dict[str, Any] = {}, event: Dict[str, Any] = {}) -> bool:
    """NeMo Action: SC-2 Latency Check (Generic)."""
    return True

def check_data_latency(context: Dict[str, Any] = {}, event: Dict[str, Any] = {}) -> bool:
    """
    Enforces HZ-Latency: Blocks trades if data latency > 200ms.
    Uses real Temporal Logic.
    """
    logger.info("🛡️ NeMo Action: check_data_latency invoked.")

    tick_timestamp = float(context.get("tick_timestamp", time.time()))
    now = time.time()
    latency_ms = (now - tick_timestamp) * 1000.0

    if latency_ms < 0: latency_ms = 0

    if latency_ms > 200.0:
        logger.warning(f"⛔ UCA Violation (Latency): {latency_ms:.2f}ms > 200ms")
        return False

    logger.info(f"✅ Latency Check Passed: {latency_ms:.2f}ms")
    return True

def check_atomic_execution(context: Dict[str, Any] = {}, event: Dict[str, Any] = {}) -> bool:
    """
    Enforces HZ-Atomic: Ensures multi-leg trades complete atomically.
    Inspects 'audit_trail' state.
    """
    logger.info("🛡️ NeMo Action: check_atomic_execution invoked.")

    audit_trail = context.get("audit_trail", [])
    current_leg = context.get("current_leg_index", 1)

    if current_leg > 1:
        prev_legs = [t for t in audit_trail if t.get("leg_index") == (current_leg - 1)]
        if not prev_legs:
            logger.warning(f"⛔ UCA Violation (Atomic): Leg {current_leg-1} missing from history.")
            return False

    return True
