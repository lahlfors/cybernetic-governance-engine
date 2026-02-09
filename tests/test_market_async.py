import pytest
import asyncio
from unittest.mock import MagicMock, patch
from src.gateway.core.market import MarketService

@pytest.mark.asyncio
async def test_check_status_async_returns_result():
    service = MarketService()

    # Mock check_status
    with patch.object(service, 'check_status') as mock_sync_check:
        mock_sync_check.return_value = "OPEN: AAPL $150.00"

        result = await service.check_status_async("AAPL")

        assert result == "OPEN: AAPL $150.00"
        mock_sync_check.assert_called_once_with("AAPL")

@pytest.mark.asyncio
async def test_check_status_async_is_non_blocking():
    # Verify that it runs in a thread
    service = MarketService()

    with patch("asyncio.to_thread") as mock_to_thread:
        await service.check_status_async("AAPL")
        mock_to_thread.assert_called_once_with(service.check_status, "AAPL")
