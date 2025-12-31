from pydantic import BaseModel, Field, field_validator
from financial_advisor.governance import governed_tool

class TradeOrder(BaseModel):
    """
    Schema for financial trading actions.
    """
    symbol: str = Field(..., description="Ticker symbol of the asset")
    amount: float = Field(..., description="Amount to trade")
    currency: str = Field(..., description="Currency code (e.g. USD, EUR)")

    @field_validator('amount')
    @classmethod
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v

@governed_tool(action_name="execute_trade")
def execute_trade(order: TradeOrder) -> str:
    """
    Executes a trade on the exchange.
    Requires Governance Approval (OPA) before running.
    """
    return f"SUCCESS: Executed trade for {order.amount} {order.currency} of {order.symbol}."
