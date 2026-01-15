import logging
from typing import Dict, Any, List, Optional
from src.governance.safety import safety_filter

logger = logging.getLogger("NeMo.Actions")

# --- CORE/EXISTING ACTIONS ---

def check_approval_token(context: Dict[str, Any] = {}, event: Dict[str, Any] = {}) -> bool:
    """NeMo Action: SC-1 Authorization Check."""
    logger.info("🛡️ NeMo Action: check_approval_token invoked.")
    token = context.get("approval_token")
    if token == "valid_token": return True
    logger.warning("⛔ SC-1 Violation: Invalid/Missing token.")
    return False

def check_latency(context: Dict[str, Any] = {}, event: Dict[str, Any] = {}) -> bool:
    """NeMo Action: SC-2 Latency Check (Generic)."""
    # ... existing implementation ...
    return True

# --- REFINED FINANCIAL ACTIONS (Target State from Transpiler) ---

def check_slippage_risk(context: Dict[str, Any] = {}, event: Dict[str, Any] = {}) -> bool:
    """
    Enforces HZ-04: Blocks market orders exceeding 1% of daily volume.
    """
    logger.info("🛡️ NeMo Action: check_slippage_risk invoked.")

    order_type = context.get("order_type", "MARKET")
    order_size = float(context.get("order_size", 0))
    daily_vol = float(context.get("daily_volume", 1000000))

    if order_type == "MARKET" and order_size > (daily_vol * 0.01):
        logger.warning(f"⛔ UCA Violation (Slippage): Order {order_size} > 1% of {daily_vol}")
        return False

    return True

def check_drawdown_limit(context: Dict[str, Any] = {}, event: Dict[str, Any] = {}) -> bool:
    """
    Enforces HZ-Drawdown: Blocks buy orders if drawdown > 4.5%.
    """
    logger.info("🛡️ NeMo Action: check_drawdown_limit invoked.")
    current_drawdown = float(context.get("drawdown_pct", 0.0))

    if current_drawdown > 4.5:
        logger.warning(f"⛔ UCA Violation (Drawdown): {current_drawdown}% > 4.5%")
        return False
    return True

def check_data_latency(context: Dict[str, Any] = {}, event: Dict[str, Any] = {}) -> bool:
    """
    Enforces HZ-Latency: Blocks trades if data latency > 200ms.
    """
    logger.info("🛡️ NeMo Action: check_data_latency invoked.")
    # In prod, diff context['tick_timestamp'] vs now()
    current_latency = float(context.get("latency_ms", 50.0))

    if current_latency > 200.0:
        logger.warning(f"⛔ UCA Violation (Latency): {current_latency}ms > 200ms")
        return False
    return True

def check_atomic_execution(context: Dict[str, Any] = {}, event: Dict[str, Any] = {}) -> bool:
    """
    Enforces HZ-Atomic: Ensures multi-leg trades complete atomically.
    """
    logger.info("🛡️ NeMo Action: check_atomic_execution invoked.")
    legs_completed = int(context.get("legs_completed", 2))
    legs_required = int(context.get("legs_required", 2))

    if legs_completed < legs_required:
        logger.warning(f"⛔ UCA Violation (Atomic): {legs_completed}/{legs_required} legs")
        return False
    return True
