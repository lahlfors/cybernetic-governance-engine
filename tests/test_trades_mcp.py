import asyncio
import logging
import sys
import os

# Adjust path
sys.path.append(os.getcwd())

from src.governed_financial_advisor.tools.trades import execute_trade

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestTradesMCP")

async def test_trade_execution():
    logger.info("--- Testing Trade Execution (MCP Integration) ---")
    
    # Mock Order
    order = {
        "symbol": "AAPL",
        "amount": 10,
        "currency": "USD",
        "transaction_id": "test-txn-001",
        "confidence": 0.95
    }

    # Execute Trade
    logger.info(f"Executing Trade: {order}")
    try:
        # This calls trades.py -> mcp_client -> Gateway -> execute_trade_action
        # The Gateway might fail if it tries to execute for real, or block if governance fails.
        # But we just want to see if the call succeeds.
        res = await execute_trade(order)
        logger.info(f"✅ Trade Result: {res}")
    except Exception as e:
        logger.error(f"❌ Trade Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_trade_execution())
