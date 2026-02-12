import logging
from typing import Any

logger = logging.getLogger("NeMo.Actions")

# --- STUBBED ACTIONS ---
# Governance logic has been moved to src/gateway/governance/
# These actions return True to allow the Agent to proceed to the Tool Execution phase,
# where the Gateway will enforce the actual constraints.

def check_approval_token(context: dict[str, Any] = {}, event: dict[str, Any] = {}) -> bool:
    """
    Stub: Delegated to Gateway (SC-1).
    """
    logger.debug("🛡️ NeMo Action Stub: check_approval_token (Allowed)")
    return True

def check_latency(context: dict[str, Any] = {}, event: dict[str, Any] = {}) -> bool:
    """Stub: Delegated to Gateway (SC-2)."""
    return True

def check_data_latency(context: dict[str, Any] = {}, event: dict[str, Any] = {}) -> bool:
    """
    Stub: Delegated to Gateway (HZ-Latency).
    """
    logger.debug("🛡️ NeMo Action Stub: check_data_latency (Allowed)")
    return True

def check_drawdown_limit(context: dict[str, Any] = {}, event: dict[str, Any] = {}) -> bool:
    """
    Stub: Delegated to Gateway (HZ-Drawdown).
    """
    logger.debug("🛡️ NeMo Action Stub: check_drawdown_limit (Allowed)")
    return True

def check_atomic_execution(context: dict[str, Any] = {}, event: dict[str, Any] = {}) -> bool:
    """
    Stub: Delegated to Gateway (HZ-Atomic).
    """
    logger.debug("🛡️ NeMo Action Stub: check_atomic_execution (Allowed)")
    return True

def check_slippage_risk(context: dict[str, Any] = {}, event: dict[str, Any] = {}) -> bool:
    """
    Stub: Delegated to Gateway (HZ-Slippage).
    """
    logger.debug("🛡️ NeMo Action Stub: check_slippage_risk (Allowed)")
    return True

# Helper to avoid import errors if anything tries to import it
def _get_drawdown_limit() -> float:
    return 0.05
