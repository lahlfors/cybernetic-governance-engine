from pydantic import BaseModel, Field, field_validator
from financial_advisor.governance import governed_tool
import re
import uuid

class TradeOrder(BaseModel):
    """
    Schema for financial trading actions.
    """
    transaction_id: str = Field(..., description="Unique UUID for the transaction")
    trader_id: str = Field(..., description="ID of the trader initiating the request (e.g. 'trader_001')")
    trader_role: str = Field(..., description="Role of the trader: 'junior' or 'senior'")
    symbol: str = Field(..., description="Ticker symbol of the asset")
    amount: float = Field(..., description="Amount to trade")
    currency: str = Field(..., description="Currency code (e.g. USD, EUR)")

    @field_validator('amount')
    @classmethod
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v

    @field_validator('transaction_id')
    @classmethod
    def validate_uuid(cls, v):
        # Regex for UUID v4
        uuid_regex = r"^[0-9a-f]{8}-[0-9a-f]{4}-[4][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        if not re.match(uuid_regex, v.lower()):
            raise ValueError("Invalid transaction_id format. Must be a valid UUID v4.")
        return v

    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v):
        # Regex for Ticker Symbol (1-5 Uppercase letters)
        if not re.match(r"^[A-Z]{1,5}$", v):
            raise ValueError("Invalid symbol format. Must be 1-5 uppercase letters.")
        return v

    @field_validator('trader_role')
    @classmethod
    def validate_role(cls, v):
        if v.lower() not in ["junior", "senior"]:
             raise ValueError("Invalid role. Must be 'junior' or 'senior'.")
        return v.lower()


@governed_tool(action_name="propose_trade")
def propose_trade(order: TradeOrder) -> str:
    """
    Proposes a trade strategy. This does NOT execute the trade.
    It submits the order for verification and policy checks.
    """
    return f"PROPOSAL LOGGED: {order.symbol} {order.amount} {order.currency}. Transaction ID: {order.transaction_id}. Waiting for Verifier."

@governed_tool(action_name="execute_trade")
def execute_trade(order: TradeOrder) -> str:
    """
    Executes a trade on the exchange.
    Requires Governance Approval (OPA) before running.
    """
    return f"SUCCESS: Executed trade {order.transaction_id} for {order.amount} {order.currency} of {order.symbol}."
