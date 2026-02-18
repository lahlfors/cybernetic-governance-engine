import os
from unittest.mock import patch

import httpx
import pytest
import respx

from src.gateway.core.market import MarketService


@pytest.fixture
def market_service():
    with patch.dict(os.environ, {"ALPHAVANTAGE_API_KEY": "dummy_key"}):
        return MarketService()

@pytest.mark.asyncio
async def test_get_sentiment(market_service):
    symbol = "AAPL"
    url = "https://www.alphavantage.co/query"

    mock_response = {
        "feed": [
            {"title": "Apple does good", "overall_sentiment_score": 0.8, "overall_sentiment_label": "Bullish"},
            {"title": "Apple does ok", "overall_sentiment_score": 0.1, "overall_sentiment_label": "Neutral"}
        ]
    }

    with respx.mock(base_url=url) as respx_mock:
        respx_mock.get("/", params={"function": "NEWS_SENTIMENT", "tickers": symbol, "apikey": "dummy_key", "limit": 5}).mock(return_value=httpx.Response(200, json=mock_response))

        sentiment = await market_service.get_sentiment(symbol)
        assert "Market Sentiment for AAPL:" in sentiment
        assert "Bullish (0.8)" in sentiment
        assert "Neutral (0.1)" in sentiment

@pytest.mark.asyncio
async def test_check_status_async(market_service):
    symbol = "AAPL"
    url = "https://www.alphavantage.co/query"

    mock_response = {
        "Global Quote": {
            "05. price": "150.00",
            "10. change percent": "1.5%"
        }
    }

    with respx.mock(base_url=url) as respx_mock:
        # Note: respx mocks async by default, but also works for sync if using httpx
        respx_mock.get("/", params={"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": "dummy_key"}).mock(return_value=httpx.Response(200, json=mock_response))

        status = await market_service.check_status_async(symbol)
        assert "OPEN: AAPL trading at $150.00 (1.5%)" in status

def test_check_status_sync_compatibility(market_service):
    """Verifies that the legacy synchronous method still works."""
    symbol = "GOOGL"
    url = "https://www.alphavantage.co/query"

    mock_response = {
        "Global Quote": {
            "05. price": "200.00",
            "10. change percent": "2.0%"
        }
    }

    with respx.mock(base_url=url) as respx_mock:
        # respx mocks work for sync calls too
        respx_mock.get("/", params={"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": "dummy_key"}).mock(return_value=httpx.Response(200, json=mock_response))

        status = market_service.check_status(symbol)
        assert "OPEN: GOOGL trading at $200.00 (2.0%)" in status
