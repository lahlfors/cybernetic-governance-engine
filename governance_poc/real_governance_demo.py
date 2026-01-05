import functools
import logging
import requests
from pydantic import BaseModel, field_validator

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("GovernanceSystem")

# ==========================================
# 1. REAL OPA Client (Layer 2)
# ==========================================

class OPAClient:
    """
    Connects to a real running OPA server.
    """
    def __init__(self, url: str = "http://localhost:8181/v1/data/finance/allow"):
        self.url = url

    def check_policy(self, input_data: dict) -> bool:
        """
        Sends the input data to the OPA Engine for a decision.
        """
        try:
            # OPA expects the payload to be wrapped in "input"
            payload = {"input": input_data}

            # The actual HTTP call to the policy engine
            response = requests.post(self.url, json=payload)
            response.raise_for_status()

            # OPA returns JSON like: {"result": true} or {"result": false}
            result = response.json().get("result", False)

            logger.info(f"[OPA Server] Checked Policy. Decision: {'ALLOW' if result else 'DENY'}")
            return result

        except requests.exceptions.RequestException as e:
            logger.critical(f"[OPA Server] Connection Failed: {e}")
            return False

# Instantiate the real client
opa_client = OPAClient()


# ==========================================
# 2. Governed Tool Decorator
# ==========================================

def governed_tool(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Helper to find the Pydantic model
        model_instance = None
        for arg in args:
            if isinstance(arg, BaseModel):
                model_instance = arg
                break
        if not model_instance:
            for _, value in kwargs.items():
                if isinstance(value, BaseModel):
                    model_instance = value
                    break

        if not model_instance:
            raise ValueError("Tool must be called with a Pydantic model.")

        # --- Layer 2 Check ---
        logger.info(f"[Governance] Requesting approval for: {model_instance}")
        is_allowed = opa_client.check_policy(model_instance.model_dump())

        if not is_allowed:
            return f"BLOCKED: OPA Policy Violation. Transaction details: {model_instance.model_dump()}"

        return func(*args, **kwargs)

    return wrapper


# ==========================================
# 3. Pydantic Model (Layer 1)
# ==========================================

class TradeOrder(BaseModel):
    symbol: str
    amount: float
    currency: str

    @field_validator('amount')
    @classmethod
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v


# ==========================================
# 4. The Tool
# ==========================================

@governed_tool
def execute_trade(order: TradeOrder) -> str:
    # This only runs if OPA returns True
    return f"SUCCESS: Executed trade for {order.amount} {order.currency} of {order.symbol}."


# ==========================================
# 5. Simulation Logic
# ==========================================

if __name__ == "__main__":
    print("--- 1. Testing Valid Trade ---")
    valid_order = TradeOrder(symbol="AAPL", amount=50000, currency="USD")
    print(execute_trade(valid_order))

    print("\n--- 2. Testing High Value Trade (Policy Violation) ---")
    # This should be blocked because amount > 1,000,000
    huge_order = TradeOrder(symbol="GOOG", amount=2000000, currency="USD")
    print(execute_trade(huge_order))

    print("\n--- 3. Testing Restricted Asset (Policy Violation) ---")
    # This should be blocked because currency is BTC
    crypto_order = TradeOrder(symbol="BTC", amount=100, currency="BTC")
    print(execute_trade(crypto_order))
