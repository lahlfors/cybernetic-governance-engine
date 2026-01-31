"""
Gateway Core: Market Data Service (Simulation / Stub)
"""
import logging
import random

logger = logging.getLogger("Gateway.Market")

# Real-world market simulation stub
# In a real system, this would call a provider like Polygon.io or Bloomberg.
class MarketService:
    def check_status(self, symbol: str) -> str:
        """
        Checks if the market is open and liquid for the given symbol.
        """
        symbol = symbol.upper()
        logger.info(f"Checking market status for {symbol}...")

        # Simulation:
        # 1. Block known "CLOSED" or "HALTED" symbols
        if symbol in ["CLOSED", "HALTED", "TEST_CLOSED"]:
            return "MARKET_CLOSED: Exchange is currently closed or symbol is halted."

        # 2. Randomly simulate liquidity issues (for resilience testing)
        # In production, this would be real data.
        # For this refactor, we remove the "Mock" feel by making it a service method
        # that could be easily swapped for a real API call.

        # Check time (stubbed to always be open during business hours)
        # from datetime import datetime
        # now = datetime.now()
        # if now.hour < 9 or now.hour > 16:
        #    return "MARKET_CLOSED: Outside trading hours."

        return f"MARKET_OPEN: {symbol} is trading. Liquidity is sufficient."

market_service = MarketService()
