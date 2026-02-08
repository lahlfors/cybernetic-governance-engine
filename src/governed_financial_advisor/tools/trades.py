import logging
from src.gateway.core.structs import TradeOrder
from src.governed_financial_advisor.infrastructure.gateway_client import gateway_client

logger = logging.getLogger(__name__)

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
