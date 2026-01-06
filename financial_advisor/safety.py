import logging
from typing import Dict, Any, Optional
from financial_advisor.infrastructure.redis_client import redis_client

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

    def _get_current_cash(self) -> float:
        return redis_client.get_float(self.redis_key, 100000.0)

    def get_h(self, cash_balance: float) -> float:
        """
        Safety Function h(x). Safe if h(x) >= 0.
        """
        return cash_balance - self.min_cash_balance

    def verify_action(self, action_name: str, payload: Dict[str, Any]) -> str:
        """
        Verifies if the action is safe relative to the *shared* state in Redis.
        """
        # 1. Fetch State (Hot Path)
        current_cash = self._get_current_cash()

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

        print(f"DEBUG: Cash: {current_cash} -> {next_cash}")
        print(f"DEBUG: h(t): {h_t}, h(next): {h_next}, required: {required_h_next}")
        print(f"DEBUG: Gamma: {self.gamma}")

        logger.info(f"🛡️ CBF Check | Cash: {current_cash} -> {next_cash}")

        # 4. Verify Condition: h(next) >= (1-gamma) * h(current)
        if h_next >= required_h_next and h_next >= 0:
            return "SAFE"

        return f"UNSAFE: CBF violation. h(next)={h_next} < threshold={required_h_next}"

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
