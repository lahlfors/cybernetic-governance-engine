import httpx
import pytest
import respx

from src.gateway.core.policy import OPAClient


@pytest.mark.asyncio
async def test_opa_allow():
    async with respx.mock(base_url="http://localhost") as mock:
        mock.post("/v1/data/finance/decision").mock(return_value=httpx.Response(200, json={"result": "ALLOW"}))

        opa_client = OPAClient()
        result = await opa_client.evaluate_policy({"action": "test"})
        assert result == "ALLOW"

@pytest.mark.asyncio
async def test_opa_deny():
    async with respx.mock(base_url="http://localhost") as mock:
        mock.post("/v1/data/finance/decision").mock(return_value=httpx.Response(200, json={"result": "DENY"}))

        opa_client = OPAClient()
        result = await opa_client.evaluate_policy({"action": "test"})
        assert result == "DENY"

@pytest.mark.asyncio
async def test_circuit_breaker():
    async with respx.mock(base_url="http://localhost") as mock:
        # Simulate 5 failures
        mock.post("/v1/data/finance/decision").mock(return_value=httpx.Response(500))

        opa_client = OPAClient()

        # Reset CB (just in case, though new instance starts closed)
        opa_client.cb.state = "CLOSED"
        opa_client.cb.failures = 0

        for _ in range(5):
            result = await opa_client.evaluate_policy({"action": "test"})
            assert result == "DENY"

        # Now CB should be OPEN
        assert opa_client.cb.state == "OPEN"
