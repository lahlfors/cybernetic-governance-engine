import json
from typing import Any
# --- CACHING STATE ---
_safety_params_cache: dict[str, Any] = {}
_last_check_time: float = 0.0
CACHE_TTL = 5.0  # Seconds

import logging
import os
import time
from typing import Any

# --- STATIC CBF CONSTANTS ---
SAFETY_PARAMS_FILE = "src/gateway/governance/safety_params.json"
DEFAULT_DRAWDOWN_LIMIT = 0.05  # 5% default fallback

from src.governed_financial_advisor.infrastructure.redis_client import redis_client
from src.governed_financial_advisor.utils.telemetry import get_tracer

logger = logging.getLogger("SafetyLayer")

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

class ControlBarrierFunction:
    """
    Implements a discrete-time Control Barrier Function (CBF).

    CRITICAL: Uses Redis for state persistence.
    In Cloud Run (Stateless), local variables reset on every request.
    We MUST fetch `current_cash` from Redis for every verification.
    """

    def __init__(self, min_cash_balance: float = 1000.0, gamma: float = 0.5):
        self.min_cash_balance = min_cash_balance
        self.gamma = gamma
        self.redis_key = "safety:current_cash"

        # Bootstrap state if empty (e.g. first run)
        if redis_client.get(self.redis_key) is None:
            redis_client.set(self.redis_key, "100000.0")

        self.tracer = get_tracer()

    def _get_current_cash(self) -> float:
        return redis_client.get_float(self.redis_key, 100000.0)

    def get_h(self, cash_balance: float) -> float:
        """
        Safety Function h(x). Safe if h(x) >= 0.
        """
        return cash_balance - self.min_cash_balance

    def verify_action(self, action_name: str, payload: dict[str, Any]) -> str:
        """
        Verifies if the action is safe relative to the *shared* state in Redis.
        """
        # 1. Fetch State (Hot Path)
        current_cash = self._get_current_cash()

        # Wrap logic in trace
        if self.tracer:
             with self.tracer.start_as_current_span("safety.cbf_check") as span:
                 return self._do_verify_action(action_name, payload, current_cash, span)
        else:
             return self._do_verify_action(action_name, payload, current_cash, None)

    def _do_verify_action(self, action_name: str, payload: dict[str, Any], current_cash: float, span) -> str:
        if span:
             span.set_attribute("safety.cash.current", current_cash)

        # 2. Calculate Next State
        cost = 0.0
        if action_name == "execute_trade":
            # Assuming 'amount' is cash cost for this safety check
            cost = payload.get("amount", 0.0)

        next_cash = current_cash - cost

        # 3. Calculate Barrier
        h_t = self.get_h(current_cash)
        h_next = self.get_h(next_cash)
        required_h_next = (1.0 - self.gamma) * h_t

        logger.info(f"🛡️ CBF Check | Cash: {current_cash} -> {next_cash}")

        # 4. Verify Condition: h(next) >= (1-gamma) * h(current)
        # 4. Verify Condition: h(next) >= (1-gamma) * h(current)
        result = "SAFE"
        is_bankruptcy = False
        if h_next < required_h_next or h_next < 0:
             result = f"UNSAFE: CBF violation. h(next)={h_next} < threshold={required_h_next}"
             # Bankruptcy occurs when cash would go below minimum
             if h_next < 0:
                 if span:
                     span.set_attribute("event.bankruptcy", True)
                     span.set_attribute("safety.bankruptcy_deficit", abs(h_next))

        if span:
             span.set_attribute("safety.cash.next", next_cash)
             span.set_attribute("safety.barrier.h_next", h_next)
             span.set_attribute("safety.result", result)
             # Bankruptcy monitor attribute for Langfuse dashboard
             if is_bankruptcy:
                 span.set_attribute("event.bankruptcy", True)
                 span.set_attribute("safety.bankruptcy_deficit", abs(h_next))

        # 5. Drawdown Check (Merged from Backend)
        # Check if 'drawdown_pct' is in payload (e.g. from market data context)
        if "drawdown_pct" in payload:
            limit = _get_drawdown_limit()
            raw_drawdown = float(payload.get("drawdown_pct", 0.0))
            current_drawdown = raw_drawdown / 100.0
            barrier_value = limit - current_drawdown
            
            if barrier_value < 0:
                msg = f"UNSAFE: Drawdown Violation. {current_drawdown:.2%} > Limit {limit:.2%}"
                logger.warning(f"⛔ {msg}")
                if result == "SAFE":
                    result = msg
                else:
                    result += f"; {msg}"

        return result

    def update_state(self, cost: float):
        """
        Commits the new state to Redis after successful execution.
        """
        # Note: In high-concurrency production, use Redis transactions (WATCH/MULTI).
        # For this implementation, simple SET is used.
        current = self._get_current_cash()
        new_balance = current - cost
        redis_client.set(self.redis_key, str(new_balance))
        logger.info(f"✅ State Updated: Cash balance is now {new_balance}")

    def rollback_state(self, cost: float):
        """
        Reverts state after a failed execution (e.g., broker API error).
        Call this when a trade was approved but failed downstream.
        """
        current = self._get_current_cash()
        restored_balance = current + cost
        redis_client.set(self.redis_key, str(restored_balance))
        logger.info(f"🔄 State Rolled Back: Cash balance restored to {restored_balance}")

# Global instance
safety_filter = ControlBarrierFunction()
