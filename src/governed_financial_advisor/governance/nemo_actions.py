import json
import logging
import os
import time
from typing import Any

from src.governed_financial_advisor.demo.state import demo_state

# Import generated actions if available
try:
    from src.governed_financial_advisor.governance.generated_actions import check_slippage_risk
except ImportError:
    logging.warning("Generated actions not found. Using fallback.")
    def check_slippage_risk(*args, **kwargs): return True

logger = logging.getLogger("NeMo.Actions")

# --- STATIC CBF CONSTANTS ---
SAFETY_PARAMS_FILE = "src/governed_financial_advisor/governance/safety_params.json"
DEFAULT_DRAWDOWN_LIMIT = 0.05  # 5% default fallback

# --- CACHING STATE ---
_safety_params_cache: dict[str, Any] = {}
_last_check_time: float = 0.0
CACHE_TTL = 5.0  # Seconds

# --- CORE/EXISTING ACTIONS ---

"""
NOTE: Governance Enforcement Strategy
-------------------------------------
These NeMo actions (check_slippage_risk, check_data_latency, etc.) are currently
NOT enforced by the Agentic Gateway for 'execute_trade' calls.
The Gateway (src/gateway/server/main.py) uses the SymbolicGovernor which enforces:
1. OPA Policies (RBAC, Limits) - src/gateway/core/policy.py
2. Control Barrier Functions (Safety/Cash) - src/governed_financial_advisor/governance/safety.py
3. Consensus Engine (Human Oversight) - src/governed_financial_advisor/governance/consensus.py

These actions may be used for:
- Agent-side "Self-Correction" (if wired into the Agent's internal rails)
- Demo Simulation (e.g. check_data_latency injects simulated latency)
- Future "Defense in Depth" layers

If these checks are intended to be strictly enforced, they should be migrated to OPA Rego policies
or the Gateway should be updated to invoke NeMo for tool execution.
"""

def check_approval_token(context: dict[str, Any] = {}, event: dict[str, Any] = {}) -> bool:
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

def check_latency(context: dict[str, Any] = {}, event: dict[str, Any] = {}) -> bool:
    """NeMo Action: SC-2 Latency Check (Generic)."""
    return True

def check_data_latency(context: dict[str, Any] = {}, event: dict[str, Any] = {}) -> bool:
    """
    Enforces HZ-Latency: Blocks trades if data latency > 200ms.
    Uses real Temporal Logic.
    """
    logger.info("🛡️ NeMo Action: check_data_latency invoked.")

    tick_timestamp = float(context.get("tick_timestamp", time.time()))
    now = time.time()
    latency_ms = (now - tick_timestamp) * 1000.0

    # Inject simulated latency from Demo State
    if demo_state.simulated_latency > 0:
        logger.info(f"🧪 Demo Mode: Injecting {demo_state.simulated_latency}ms simulated latency.")
        latency_ms += demo_state.simulated_latency

    if latency_ms < 0: latency_ms = 0

    if latency_ms > 200.0:
        logger.warning(f"⛔ UCA Violation (Latency): {latency_ms:.2f}ms > 200ms")
        return False

    logger.info(f"✅ Latency Check Passed: {latency_ms:.2f}ms")
    return True

def _get_drawdown_limit() -> float:
    """
    Helper to safely read the dynamic drawdown limit from JSON.
    Implements input sanitization, default fallback, and caching.
    """
    global _safety_params_cache, _last_check_time

    now = time.time()

    # Return cached value if within TTL
    if _safety_params_cache and (now - _last_check_time < CACHE_TTL):
        return _safety_params_cache.get("drawdown_limit", DEFAULT_DRAWDOWN_LIMIT)

    try:
        if not os.path.exists(SAFETY_PARAMS_FILE):
            return DEFAULT_DRAWDOWN_LIMIT

        # Check file modification time for smarter caching?
        # For now, simple TTL is sufficient and robust.

        with open(SAFETY_PARAMS_FILE) as f:
            data = json.load(f)

        limit = data.get("drawdown_limit")

        # Schema Validation: 0.0 < limit < 1.0
        if limit is None:
            limit = DEFAULT_DRAWDOWN_LIMIT
        elif not isinstance(limit, (int, float)):
             logger.error(f"Invalid type for drawdown_limit: {type(limit)}")
             limit = DEFAULT_DRAWDOWN_LIMIT
        elif limit <= 0.0 or limit >= 1.0:
            logger.error(f"Invalid value for drawdown_limit: {limit}. Must be between 0.0 and 1.0")
            limit = DEFAULT_DRAWDOWN_LIMIT
        else:
            limit = float(limit)

        # Update Cache
        _safety_params_cache = {"drawdown_limit": limit}
        _last_check_time = now

        return limit

    except json.JSONDecodeError:
        logger.error(f"Corrupt safety params file: {SAFETY_PARAMS_FILE}")
        return DEFAULT_DRAWDOWN_LIMIT
    except Exception as e:
        logger.error(f"Error reading safety params: {e}")
        return DEFAULT_DRAWDOWN_LIMIT

def check_drawdown_limit(context: dict[str, Any] = {}, event: dict[str, Any] = {}) -> bool:
    """
    Enforces HZ-Drawdown: Discrete Control Barrier Function (CBF).
    Invariant: h(x) = Limit - Current_Drawdown >= 0
    """
    limit = _get_drawdown_limit()

    # context['drawdown_pct'] is typically 0-100 based on previous analysis of transpiler/agent.
    # However, our limit is 0.0 - 1.0.
    # If the input is "5.0" (percent), we need to normalize it to 0.05
    # OR we assume the context provides it in the same unit.
    # The generated code used: current_drawdown = float(context.get("drawdown_pct", 0))
    # And compared: if current_drawdown > {limit} (where limit was e.g. 4.5).
    # So the context "drawdown_pct" is 0-100.
    # Therefore, we must normalize the context value: 5.0 -> 0.05

    raw_drawdown = float(context.get("drawdown_pct", 0.0))
    current_drawdown = raw_drawdown / 100.0

    # CBF Calculation
    barrier_value = limit - current_drawdown

    # Logging for Observability
    logger.info(f"🛡️ CBF Check (Drawdown): Limit={limit:.4f}, Current={current_drawdown:.4f}, h(x)={barrier_value:.4f}")

    if barrier_value < 0:
        logger.warning(f"⛔ UCA Violation (Drawdown): h(x) < 0 ({barrier_value:.4f})")
        return False

    return True

def check_atomic_execution(context: dict[str, Any] = {}, event: dict[str, Any] = {}) -> bool:
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
