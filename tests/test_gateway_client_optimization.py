from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Reset singleton before importing to ensure clean state
try:
    from src.governed_financial_advisor.infrastructure.gateway_client import (
        GatewayClient,
    )
    GatewayClient._instance = None
except ImportError:
    pass

@pytest.mark.asyncio
async def test_gateway_client_reuses_httpx_client():
    """
    Verifies that GatewayClient reuses the underlying httpx.AsyncClient
    instead of creating a new one for every request.
    """

    # Mock response object (what await client.post(...) returns)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"choices": [{"message": {"content": "mock_response"}}]}
    mock_response.raise_for_status.return_value = None

    # Patch httpx.AsyncClient in the module
    with patch("src.governed_financial_advisor.infrastructure.gateway_client.httpx.AsyncClient") as MockAsyncClient:
        # Create the mock client instance
        mock_client_instance = AsyncMock()
        # client.post(...) is awaited, so it should return the response
        mock_client_instance.post.return_value = mock_response

        # Setup for 'async with httpx.AsyncClient() as client':
        # MockAsyncClient() returns the context manager object.
        # Its __aenter__ method should be awaitable and return the client instance.
        mock_context_manager = MagicMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        MockAsyncClient.return_value = mock_context_manager

        # BUT: For the NEW implementation, we might not use context manager.
        # We might use `self.client = httpx.AsyncClient()`.
        # In that case MockAsyncClient() should return mock_client_instance directly?
        # No, httpx.AsyncClient() returns the client instance, which is also a context manager.
        # So the object returned by constructor IS the client.

        # So let's make the constructor return our mock_client_instance.
        # And make mock_client_instance support __aenter__/__aexit__ for the OLD code.
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)

        MockAsyncClient.return_value = mock_client_instance

        # Reset singleton to ensure __new__ runs fully
        GatewayClient._instance = None
        client = GatewayClient()

        # Call chat 3 times
        await client.chat("test1")
        await client.chat("test2")
        await client.chat("test3")

        print(f"AsyncClient instantiation count: {MockAsyncClient.call_count}")

        # In unoptimized code: AsyncClient() called 3 times.
        # In optimized code: AsyncClient() called 1 time.

        # Check assertions logic:
        # If unoptimized, it will be called 3 times.
        if MockAsyncClient.call_count > 1:
             print("Test confirming UNOPTIMIZED behavior (multiple instantiations).")
             # We want this test to pass ONLY when optimized.
             # So we assert == 1.

        assert MockAsyncClient.call_count == 1, f"Expected 1 client instantiation, got {MockAsyncClient.call_count}"

        # Verify post was called 3 times
        assert mock_client_instance.post.call_count == 3
