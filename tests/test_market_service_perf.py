import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import httpx
from src.gateway.core.market import MarketService

@pytest.mark.asyncio
async def test_market_service_reuses_http_client():
    # Patch both AsyncClient and Client at the class level
    with patch("httpx.AsyncClient") as mock_async_cls, \
         patch("httpx.Client") as mock_sync_cls:

        # Setup mocks
        mock_async_instance = AsyncMock()
        mock_async_cls.return_value = mock_async_instance
        # Async context manager mock
        mock_async_instance.__aenter__.return_value = mock_async_instance
        mock_async_instance.__aexit__.return_value = None

        mock_sync_instance = MagicMock()
        mock_sync_cls.return_value = mock_sync_instance
        # Sync context manager mock
        mock_sync_instance.__enter__.return_value = mock_sync_instance
        mock_sync_instance.__exit__.return_value = None

        # Setup responses
        mock_response = MagicMock()
        mock_response.json.return_value = {"feed": [{"title": "News", "overall_sentiment_score": 0.5}]}
        mock_async_instance.get.return_value = mock_response
        mock_sync_instance.get.return_value = mock_response

        # Instantiate MarketService
        # This will fail assertion if clients are NOT created in __init__ (current buggy behavior)
        # Or succeed if they ARE created in __init__ (fixed behavior)
        # Wait, if they are created in __init__, mock_cls will be called once here.
        service = MarketService()

        # In current buggy implementation, clients are NOT created in __init__.
        # So call_count should be 0 here.
        # But we want to assert that they ARE created once (after fix).
        # So this test is designing for the DESIRED behavior.

        # Let's verify current behavior first: call_count should be 0.
        # But for the final test, we want call_count == 1.

        # Call methods
        service.api_key = "TEST_KEY" # Ensure it doesn't return early

        await service.get_sentiment("AAPL")
        service.check_status("AAPL")

        await service.get_sentiment("GOOGL")
        service.check_status("GOOGL")

        # ASSERTIONS FOR OPTIMIZED BEHAVIOR:
        # 1. Clients created exactly ONCE (during init)
        assert mock_async_cls.call_count == 1, "AsyncClient should be instantiated exactly once"
        assert mock_sync_cls.call_count == 1, "Client should be instantiated exactly once"

        # 2. Get called multiple times on the SAME instance
        assert mock_async_instance.get.call_count == 2
        assert mock_sync_instance.get.call_count == 2

        # 3. Verify shutdown
        await service.shutdown()
        service.shutdown_sync()

        mock_async_instance.aclose.assert_called_once()
        mock_sync_instance.close.assert_called_once()
