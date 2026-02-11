"""
Gateway Core: Real Trade Execution Logic (Optimistic Execution with Interrupt Check)
"""

import logging
import asyncio
from pydantic import BaseModel, Field
from src.gateway.core.structs import TradeOrder
from src.governed_financial_advisor.infrastructure.redis_client import redis_client
from src.governed_financial_advisor.infrastructure.config_manager import config_manager

logger = logging.getLogger(__name__)

async def execute_trade(order: TradeOrder) -> str:
    """
    Executes a trade against a real Broker API (e.g. Alpaca).

    OPTIMISTIC EXECUTION: Checks 'safety_violation' in Redis before committing.
    CONFIG: Uses ConfigManager for secure key retrieval.
    """
    # --- INTERRUPT CHECK (Module 6) ---
    violation = redis_client.get("safety_violation")
    if violation:
        logger.warning(f"🛑 Trade INTERRUPTED by Safety Monitor: {violation}")
        raise RuntimeError(f"Trade INTERRUPTED by Safety Monitor: {violation}")

    # Secure Config Loading
    # Auto-mapping to 'broker-api-key' and 'broker-api-secret' via ConfigManager
    api_key = config_manager.get("BROKER_API_KEY")
    api_secret = config_manager.get("BROKER_API_SECRET")
    base_url = config_manager.get("BROKER_API_URL", "https://paper-api.alpaca.markets")

    if not api_key or not api_secret:
        # In Production, we fail safe if credentials are missing.
        error_msg = "Configuration Error: BROKER_API_KEY or BROKER_API_SECRET missing. Cannot execute trade."
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    logger.info(f"Executing Trade {order.transaction_id} on {base_url} (Confidence: {order.confidence})...")

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
        # --- LATE INTERRUPT CHECK (Just before HTTP call) ---
        latest_violation = redis_client.get("safety_violation")
        if latest_violation:
             raise RuntimeError(f"Trade INTERRUPTED immediately before HTTP call: {latest_violation}")

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
        # Explicitly re-raise if it's our interrupt
        if "INTERRUPTED" in str(e):
             raise RuntimeError(str(e))
        raise RuntimeError(f"Broker Execution Failed: {e}")
