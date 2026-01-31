"""
Gateway Core: Tool Execution Logic
"""
import logging
import re
import uuid
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger("Gateway.Tools")

class TradeOrder(BaseModel):
    """
    Schema for financial trading actions.
    """
    # User-provided fields
    symbol: str = Field(..., description="Ticker symbol of the asset")
    amount: float = Field(..., description="Amount to trade")
    currency: str = Field(..., description="Currency code (e.g. USD, EUR)")

    # System-generated fields with defaults
    transaction_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique UUID for the transaction")
    trader_id: str = Field(default="agent_001", description="ID of the trader initiating the request (e.g. 'trader_001')")
    trader_role: str = Field(default="junior", description="Role of the trader: 'junior' or 'senior'")

    @field_validator('amount')
    @classmethod
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v

    @field_validator('transaction_id')
    @classmethod
    def validate_uuid(cls, v):
        uuid_regex = r"^[0-9a-f]{8}-[0-9a-f]{4}-[4][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        if not re.match(uuid_regex, v.lower()):
            raise ValueError("Invalid transaction_id format. Must be a valid UUID v4.")
        return v

    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v):
        v = v.upper()
        if not re.match(r"^[A-Z]{1,5}$", v):
            raise ValueError("Invalid symbol format. Must be 1-5 letters.")
        return v

    @field_validator('trader_role')
    @classmethod
    def validate_role(cls, v):
        if v.lower() not in ["junior", "senior"]:
             raise ValueError("Invalid role. Must be 'junior' or 'senior'.")
        return v.lower()

# NOTE: The @governed_tool decorator is REMOVED.
# Governance is now applied by the Gateway Server before calling this function.

async def execute_trade(order: TradeOrder) -> str:
    """
    Executes a trade on the exchange.
    This function is now 'Action Only' - it assumes governance has passed.
    """
    logger.info(f"EXECUTING TRADE (System 1): {order.transaction_id} {order.symbol} {order.amount}")
    return f"SUCCESS: Executed trade {order.transaction_id} for {order.amount} {order.currency} of {order.symbol}."
