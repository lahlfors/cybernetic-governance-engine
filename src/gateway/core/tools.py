"""
Gateway Core: Real Trade Execution Logic
"""

import logging
import asyncio
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Re-export TradeOrder from tools/trades.py logic
class TradeOrder(BaseModel):
    # Minimal fields for execution
    symbol: str
    amount: float
    currency: str
    transaction_id: str
    trader_id: str
    trader_role: str

async def execute_trade(order: TradeOrder) -> str:
    """
    Executes a trade against a real Broker API (e.g. Alpaca).
    Currently configured to check for API keys and raise error if missing,
    ensuring no 'silent mock' success.
    """
    import os

    api_key = os.getenv("BROKER_API_KEY")
    api_secret = os.getenv("BROKER_API_SECRET")
    base_url = os.getenv("BROKER_API_URL", "https://paper-api.alpaca.markets")

    if not api_key or not api_secret:
        # In Production, we fail safe if credentials are missing.
        error_msg = "Configuration Error: BROKER_API_KEY or BROKER_API_SECRET missing. Cannot execute trade."
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    logger.info(f"Executing Trade {order.transaction_id} on {base_url}...")

    # Example using requests (simulating client lib usage for generality)
    import requests

    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": api_secret
    }

    payload = {
        "symbol": order.symbol,
        "qty": order.amount,
        "side": "buy", # Assuming buy for simple example
        "type": "market",
        "time_in_force": "day"
    }

    # We execute in a thread to avoid blocking asyncio loop with requests
    def _do_post():
        resp = requests.post(f"{base_url}/v2/orders", json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()

    try:
        # Run sync request in thread pool
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _do_post)
        logger.info(f"Trade Executed: {result.get('id')}")
        return f"EXECUTED: {order.symbol} x {order.amount} (Order ID: {result.get('id')})"

    except Exception as e:
        logger.error(f"Broker API Error: {e}")
        raise RuntimeError(f"Broker Execution Failed: {e}")
