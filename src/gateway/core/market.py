"""
Gateway Core: Market Data Service (Real Implementation)
"""

import logging
import asyncio

logger = logging.getLogger(__name__)

class MarketService:
    async def check_status_async(self, symbol: str) -> str:
        """
        Asynchronously fetches real market status and price.
        Offloads the blocking yfinance call to a thread.
        """
        return await asyncio.to_thread(self.check_status, symbol)

    def check_status(self, symbol: str) -> str:
        """
        Fetches real market status and price using yfinance.
        Lazy imports yfinance to prevent startup crashes if not installed.
        """
        try:
            logger.info(f"Fetching market data for {symbol}...")

            try:
                import yfinance as yf
            except ImportError:
                return "ERROR: yfinance library not installed. Cannot fetch market data."

            ticker = yf.Ticker(symbol)

            # Fast fetch of 'info' or 'fast_info'
            # fast_info is better for price
            price = ticker.fast_info.get('last_price', None)

            if price is None:
                # Fallback to history
                hist = ticker.history(period="1d")
                if not hist.empty:
                    price = hist['Close'].iloc[-1]

            if price:
                 return f"OPEN: {symbol} trading at ${price:.2f}"
            else:
                 return f"CLOSED/UNKNOWN: Could not fetch price for {symbol}"

        except Exception as e:
            logger.error(f"Market Data Error: {e}")
            return f"ERROR: Market data unavailable: {e}"

market_service = MarketService()
