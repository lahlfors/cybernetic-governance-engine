import httpx
import pytest
import respx

from src.gateway.core.policy import OPAClient
from config.settings import Config

@pytest.fixture
def opa_client():
    # Force URL for testing consistency or just use what's configured
    return OPAClient()

@pytest.mark.asyncio
async def test_opa_allow(opa_client):
    # Mock the full URL configured in the client
    async with respx.mock(base_url=None) as mock:
        mock.post(opa_client.url).mock(return_value=httpx.Response(200, json={"result": "ALLOW"}))

        result = await opa_client.evaluate_policy({"action": "test"})
        assert result == "ALLOW"

@pytest.mark.asyncio
async def test_opa_deny(opa_client):
    async with respx.mock(base_url=None) as mock:
        mock.post(opa_client.url).mock(return_value=httpx.Response(200, json={"result": "DENY"}))

        result = await opa_client.evaluate_policy({"action": "test"})
        assert result == "DENY"

@pytest.mark.asyncio
async def test_circuit_breaker(opa_client):
    # Reset CB
    opa_client.cb.state = "CLOSED"
    opa_client.cb.failures = 0

    async with respx.mock(base_url=None) as mock:
        # Simulate 5 failures
        mock.post(opa_client.url).mock(return_value=httpx.Response(500))

        for _ in range(5):
            result = await opa_client.evaluate_policy({"action": "test"})
            assert result == "DENY"

        # Now CB should be OPEN
        assert opa_client.cb.state == "OPEN"
