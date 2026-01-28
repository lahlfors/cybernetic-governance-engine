import logging
from typing import Any

from src.infrastructure.redis_client import redis_client
from src.utils.telemetry import get_tracer

logger = logging.getLogger("SafetyLayer")

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
        if h_next < required_h_next or h_next < 0:
             result = f"UNSAFE: CBF violation. h(next)={h_next} < threshold={required_h_next}"

        if span:
             span.set_attribute("safety.cash.next", next_cash)
             span.set_attribute("safety.barrier.h_next", h_next)
             span.set_attribute("safety.result", result)

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

# Global instance
safety_filter = ControlBarrierFunction()
