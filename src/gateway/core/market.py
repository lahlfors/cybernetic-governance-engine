import logging
import os
import httpx

logger = logging.getLogger(__name__)

class MarketService:
    def __init__(self):
        self.api_key = os.getenv("ALPHAVANTAGE_API_KEY")
        self.base_url = "https://www.alphavantage.co/query"
        # Bolt: Initialize persistent client to reuse connections (SSL/TCP)
        self.client = httpx.AsyncClient(timeout=10.0)

    async def close(self):
        """Closes the persistent HTTP client."""
        await self.client.aclose()

    async def get_sentiment(self, symbol: str) -> str:
        """
        Fetches market sentiment and news for a ticker using AlphaVantage.
        """
        if not self.api_key:
            return "ERROR: ALPHAVANTAGE_API_KEY not set. Cannot fetch sentiment."

        try:
            params = {
                "function": "NEWS_SENTIMENT",
                "tickers": symbol,
                "apikey": self.api_key,
                "limit": 5
            }
            logger.info(f"Fetching AlphaVantage sentiment for {symbol}...")
            
            # Bolt: Use persistent client
            response = await self.client.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()

            if "feed" not in data:
                # Handle cases where API returns error (e.g. rate limit)
                if "Information" in data:
                     return f"API INFO: {data['Information']}"
                if "Error Message" in data:
                     return f"API ERROR: {data['Error Message']}"
                return "No news found."

            # Summarize the news
            summary = [f"Market Sentiment for {symbol}:"]
            
            for item in data.get("feed", []):
                title = item.get("title", "No Title")
                score = item.get("overall_sentiment_score", 0)
                label = item.get("overall_sentiment_label", "Neutral")
                summary.append(f"- [{label} ({score})] {title}")

            return "\n".join(summary)

        except Exception as e:
            logger.error(f"AlphaVantage Error: {e}")
            return f"ERROR: Failed to fetch sentiment: {e}"

    def _parse_quote(self, data: dict, symbol: str) -> str:
        """Parses the global quote response."""
        # Rate Limit Check
        if "Note" in data:
            return f"LIMIT REACHED: {data['Note']}"

        quote = data.get("Global Quote", {})
        if not quote:
             return f"CLOSED/UNKNOWN: Could not fetch price for {symbol}"

        price = quote.get("05. price")
        change = quote.get("10. change percent")

        return f"OPEN: {symbol} trading at ${price} ({change})"

    async def check_status_async(self, symbol: str) -> str:
        """
        Fetches real market status and price using AlphaVantage (Global Quote) asynchronously.
        Uses persistent client to prevent blocking.
        API usage: 1 call.
        """
        # Bolt: Async version of check_status using persistent client

        if not self.api_key:
            return "ERROR: ALPHAVANTAGE_API_KEY not set."

        try:
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": symbol,
                "apikey": self.api_key
            }

            # Bolt: Use persistent client
            response = await self.client.get(self.base_url, params=params)
            data = response.json()
            return self._parse_quote(data, symbol)

        except Exception as e:
            logger.error(f"Market Data Error: {e}")
            return f"ERROR: Market data unavailable: {e}"

    def check_status(self, symbol: str) -> str:
        """
        Fetches real market status and price using AlphaVantage (Global Quote).
        API usage: 1 call.
        
        Note: This is the legacy synchronous implementation. Use check_status_async for non-blocking calls.
        """
        if not self.api_key:
            return "ERROR: ALPHAVANTAGE_API_KEY not set."

        try:
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": symbol,
                "apikey": self.api_key
            }
            
            with httpx.Client() as client:
                response = client.get(self.base_url, params=params, timeout=10.0)
                data = response.json()
            return self._parse_quote(data, symbol)

        except Exception as e:
            logger.error(f"Market Data Error: {e}")
            return f"ERROR: Market data unavailable: {e}"

market_service = MarketService()
