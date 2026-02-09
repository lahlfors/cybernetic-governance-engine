import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import httpx
from src.governed_financial_advisor.infrastructure.gateway_client import GatewayClient

@pytest.mark.asyncio
@pytest.mark.skip(reason="GatewayClient now uses gRPC, not httpx. This test needs to be rewritten.")
async def test_gateway_client_reuses_http_client():
    # We need to reset the singleton for the test
    GatewayClient._instance = None

    with patch("httpx.AsyncClient") as mock_client_cls:
        # Mock the client instance
        mock_client_instance = AsyncMock()
        mock_client_cls.return_value = mock_client_instance

        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "Test Response"}}]}
        mock_client_instance.post.return_value = mock_response

        # Instantiate GatewayClient (should trigger AsyncClient creation)
        client = GatewayClient()

        # Verify AsyncClient was created once
        mock_client_cls.assert_called_once()

        # Call chat multiple times
        await client.chat("Hello")
        await client.chat("World")

        # Verify AsyncClient was NOT created again
        mock_client_cls.assert_called_once()

        # Verify post was called twice on the SAME instance
        assert mock_client_instance.post.call_count == 2

        # Verify close
        await client.close()
        mock_client_instance.aclose.assert_called_once()
