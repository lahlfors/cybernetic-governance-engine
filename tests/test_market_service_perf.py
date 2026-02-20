from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.gateway.core.market import MarketService


@pytest.mark.asyncio
async def test_market_service_initialization():
    """Test that MarketService initializes a persistent AsyncClient."""
    ms = MarketService()
    assert isinstance(ms.client, httpx.AsyncClient)
    await ms.close()
    # Check if client is closed.
    # httpx.AsyncClient.is_closed is a property
    assert ms.client.is_closed

@pytest.mark.asyncio
async def test_check_status_async():
    """Test async check_status with mocked response."""
    ms = MarketService()

    # Mock the client.get method
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "Global Quote": {
            "05. price": "150.00",
            "10. change percent": "0.5%"
        }
    }
    mock_response.raise_for_status.return_value = None

    # Replace the get method on the instance's client
    ms.client.get = AsyncMock(return_value=mock_response)
    ms.api_key = "TEST_KEY"

    result = await ms.check_status("AAPL")

    assert "OPEN: AAPL trading at $150.00 (0.5%)" in result

    # Verify client.get was called (showing reuse)
    ms.client.get.assert_called_once()

    await ms.close()

@pytest.mark.asyncio
async def test_get_sentiment_async():
    """Test async get_sentiment with mocked response."""
    ms = MarketService()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "feed": [
            {"title": "Good News", "overall_sentiment_score": 0.8, "overall_sentiment_label": "Bullish"}
        ]
    }
    mock_response.raise_for_status.return_value = None

    ms.client.get = AsyncMock(return_value=mock_response)
    ms.api_key = "TEST_KEY"

    result = await ms.get_sentiment("AAPL")

    assert "Bullish" in result
    assert "Good News" in result

    ms.client.get.assert_called_once()

    await ms.close()

@pytest.mark.asyncio
async def test_market_service_no_api_key():
    """Test error handling when API key is missing."""
    ms = MarketService()
    ms.api_key = None # ensure it's None

    result = await ms.check_status("AAPL")
    assert "ERROR: ALPHAVANTAGE_API_KEY not set" in result

    result = await ms.get_sentiment("AAPL")
    assert "ERROR: ALPHAVANTAGE_API_KEY not set" in result

    await ms.close()
