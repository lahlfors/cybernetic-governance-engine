import re
import uuid
import logging
from pydantic import BaseModel, Field, field_validator
from src.governed_financial_advisor.infrastructure.gateway_client import gateway_client

# We keep the governance imports for `propose_trade` if it stays local,
# BUT `execute_trade` now goes to Gateway.
# If `propose_trade` also uses `governed_tool`, we need to see if `governed_tool` still works.
# For now, we will assume `propose_trade` is just a local helper and doesn't strictly need the OPA check
# (since it's just a proposal). Or we can route it too.
# The user specifically mentioned "intercept Tool Calls (execute_trade)".

logger = logging.getLogger(__name__)

class TradeOrder(BaseModel):
    """
    Schema for financial trading actions.
    """
    # User-provided fields
    symbol: str = Field(..., description="Ticker symbol of the asset")
    amount: float = Field(..., description="Amount to trade")
    currency: str = Field(..., description="Currency code (e.g. USD, EUR)")
    confidence: float = Field(..., description="Confidence score (0.0-1.0) of the agent proposing the trade. MUST be >= 0.95 for execution.")

    # System-generated fields with defaults
    transaction_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique UUID for the transaction")
    trader_id: str = Field(default="agent_001", description="ID of the trader initiating the request (e.g. 'trader_001')")
    trader_role: str = Field(default="junior", description="Role of the trader: 'junior' or 'senior'")

    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v):
        if not (0.0 <= v <= 1.0):
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v

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
        # Normalize to uppercase first
        v = v.upper()
        # Regex for Ticker Symbol (1-5 Uppercase letters)
        if not re.match(r"^[A-Z]{1,5}$", v):
            raise ValueError("Invalid symbol format. Must be 1-5 letters.")
        return v

    @field_validator('trader_role')
    @classmethod
    def validate_role(cls, v):
        if v.lower() not in ["junior", "senior"]:
             raise ValueError("Invalid role. Must be 'junior' or 'senior'.")
        return v.lower()


def propose_trade(order: TradeOrder) -> str:
    """
    Proposes a trade strategy. This does NOT execute the trade.
    """
    # Simply log it locally. No governance needed for thinking.
    return f"PROPOSAL LOGGED: {order.symbol} {order.amount} {order.currency}. Transaction ID: {order.transaction_id}. Waiting for Verifier."

async def execute_trade(order: TradeOrder) -> str:
    """
    Executes a trade via the Agentic Gateway.
    The Gateway enforces all Policy (OPA), Safety, and Consensus checks.
    """
    logger.info(f"Delegating trade execution to Gateway: {order.transaction_id} (Confidence: {order.confidence})")

    # Serialize params
    params = order.model_dump()

    # Call Gateway
    result = await gateway_client.execute_tool("execute_trade", params)

    return result
