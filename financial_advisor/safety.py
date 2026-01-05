import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("SafetyLayer")

class ControlBarrierFunction:
    """
    Implements a discrete-time Control Barrier Function (CBF) to enforce set invariance.

    Mathematical Safety Condition:
    h(x_{t+1}) >= (1 - gamma) * h(x_t)

    Where:
    - h(x): Safety function. Safe if h(x) >= 0.
    - gamma: Decay rate (0 < gamma <= 1). Determines how fast we can approach the boundary.
    """

    def __init__(self, min_cash_balance: float = 1000.0, gamma: float = 0.5):
        self.min_cash_balance = min_cash_balance
        self.gamma = gamma
        # In a real system, this state would be fetched from a DB or Portfolio Service.
        # Here we maintain a simulated local state for the agent session.
        self.current_cash = 100000.0 # Initial safe state

    def get_h(self, cash_balance: float) -> float:
        """
        Calculates the safety value h(x).
        h(x) = Current Cash - Minimum Required Cash
        Safe Set: {x | h(x) >= 0}
        """
        return cash_balance - self.min_cash_balance

    def verify_action(self, action_name: str, payload: Dict[str, Any]) -> str:
        """
        Simulates the next state x_{t+1} given the action and checks the CBF condition.
        Returns "SAFE" or "UNSAFE".
        """
        # We only care about actions that reduce cash (BUY orders)
        # Assuming payload has 'amount' and 'symbol'

        # NOTE: In a real implementation, we'd need current price to calculate cost.
        # For this simulation, we assume 'amount' is the approximate cash cost
        # OR we simplified the TradeOrder to be "amount of cash to spend".
        # Looking at TradeOrder schema, 'amount' is "Amount to trade".
        # Let's assume for this safety check that 'amount' is the DOLLAR VALUE
        # (or we interpret it conservatively as such for the simulation).

        cost = 0.0
        if action_name == "execute_trade":
            # Heuristic: Check if it's a "BUY" (Spending cash)
            # The current TradeOrder doesn't specify Buy/Sell explicitly,
            # but usually 'execute_trade' implies entering a position in this simple agent.
            # Let's assume worst case: it consumes cash.
            cost = payload.get("amount", 0.0)

        next_cash = self.current_cash - cost

        h_t = self.get_h(self.current_cash)
        h_next = self.get_h(next_cash)

        # Barrier Condition: h(x_{t+1}) - (1 - gamma) * h(x_t) >= 0
        required_h_next = (1.0 - self.gamma) * h_t

        logger.info(f"🛡️ CBF Check | Current Cash: {self.current_cash} | Cost: {cost} | Next Cash: {next_cash}")
        logger.info(f"   h(t): {h_t} | h(t+1): {h_next} | Required h(t+1): {required_h_next}")

        if h_next >= required_h_next and h_next >= 0:
            # Commit the state change (simulated) if we are allowing it
            # In a real app, this update happens after execution, but for a
            # pre-execution filter, we predict the state.
            # To avoid drift, we'd sync this with the real DB.
            return "SAFE"

        return f"UNSAFE: Control Barrier Function violation. h(next)={h_next} < threshold={required_h_next}"

    def update_state(self, cost: float):
        """Updates the internal state after a successful execution."""
        self.current_cash -= cost

# Global instance
safety_filter = ControlBarrierFunction()
