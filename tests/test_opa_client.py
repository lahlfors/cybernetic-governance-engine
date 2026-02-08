import httpx
import pytest
import respx

from src.gateway.core.policy import OPAClient


@pytest.fixture
def opa_client():
    return OPAClient()

@pytest.mark.asyncio
async def test_opa_allow(opa_client):
    async with respx.mock(base_url="http://localhost") as mock:
        mock.post("/v1/data/finance/decision").mock(return_value=httpx.Response(200, json={"result": "ALLOW"}))

        result = await opa_client.evaluate_policy({"action": "test"})
        assert result == "ALLOW"
    await opa_client.close()

@pytest.mark.asyncio
async def test_opa_deny(opa_client):
    async with respx.mock(base_url="http://localhost") as mock:
        mock.post("/v1/data/finance/decision").mock(return_value=httpx.Response(200, json={"result": "DENY"}))

        result = await opa_client.evaluate_policy({"action": "test"})
        assert result == "DENY"
    await opa_client.close()

@pytest.mark.asyncio
async def test_circuit_breaker(opa_client):
    # Reset CB
    opa_client.cb.state = "CLOSED"
    opa_client.cb.failures = 0

    async with respx.mock(base_url="http://localhost") as mock:
        # Simulate 5 failures
        mock.post("/v1/data/finance/decision").mock(return_value=httpx.Response(500))

        for _ in range(5):
            result = await opa_client.evaluate_policy({"action": "test"})
            assert result == "DENY"

        # Now CB should be OPEN
        assert opa_client.cb.state == "OPEN"
    await opa_client.close()

@pytest.mark.asyncio
async def test_opa_close(opa_client):
    await opa_client.close()
    assert opa_client.client.is_closed
