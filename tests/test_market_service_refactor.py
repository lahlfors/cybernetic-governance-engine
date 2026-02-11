import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import sys
import os

# Ensure src is in path
sys.path.append(os.getcwd())

from src.gateway.core.market import MarketService

@pytest.mark.asyncio
async def test_market_service_client_reuse():
    """
    Verifies that MarketService initializes one AsyncClient and reuses it.
    """
    # Patch env var
    with patch.dict(os.environ, {"ALPHAVANTAGE_API_KEY": "test"}):
        # Patch httpx.AsyncClient to verify instantiation count
        with patch("src.gateway.core.market.httpx.AsyncClient", autospec=True) as mock_client_cls:
            # Mock the client instance
            mock_client_instance = AsyncMock()
            mock_client_cls.return_value = mock_client_instance

            # Create service instance
            service = MarketService()

            # Verify AsyncClient was instantiated exactly once
            mock_client_cls.assert_called_once()
            assert service.client == mock_client_instance

            # Setup mock response for check_status
            mock_response_quote = MagicMock()
            mock_response_quote.json.return_value = {
                "Global Quote": {
                    "05. price": "100.00",
                    "10. change percent": "0.5%"
                }
            }
            mock_response_quote.raise_for_status = MagicMock()
            mock_client_instance.get.return_value = mock_response_quote

            # Call check_status
            status = await service.check_status("AAPL")

            # Verify result and call
            assert "AAPL" in status
            assert "100.00" in status
            mock_client_instance.get.assert_called_once() # 1st call

            # Setup mock response for get_sentiment
            mock_response_news = MagicMock()
            mock_response_news.json.return_value = {
                "feed": [
                    {
                        "title": "Positive News",
                        "overall_sentiment_score": 0.8,
                        "overall_sentiment_label": "Bullish"
                    }
                ]
            }
            mock_response_news.raise_for_status = MagicMock()
            mock_client_instance.get.return_value = mock_response_news

            # Call get_sentiment
            sentiment = await service.get_sentiment("AAPL")

            # Verify result and call
            assert "Positive News" in sentiment
            assert mock_client_instance.get.call_count == 2 # 2nd call

            # Verify closing
            await service.close()
            mock_client_instance.aclose.assert_called_once()
