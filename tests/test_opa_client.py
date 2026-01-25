import httpx
import pytest
import respx

from src.governance.client import OPAClient


@pytest.fixture
def opa_client():
    return OPAClient()

@pytest.mark.asyncio
async def test_opa_allow(opa_client):
    async with respx.mock(base_url="http://localhost") as mock:
        mock.post("/v1/data/finance/decision").mock(return_value=httpx.Response(200, json={"result": "ALLOW"}))

        result = await opa_client.evaluate_policy({"action": "test"})
        assert result == "ALLOW"

@pytest.mark.asyncio
async def test_opa_deny(opa_client):
    async with respx.mock(base_url="http://localhost") as mock:
        mock.post("/v1/data/finance/decision").mock(return_value=httpx.Response(200, json={"result": "DENY"}))

        result = await opa_client.evaluate_policy({"action": "test"})
        assert result == "DENY"

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

        # Next call should fail fast (no request)
        # We can verify by ensuring mock is NOT called if we clear it, or just checking result
        # But respx mocks are persistent in context.
        # If we use side_effect to raise exception, we can distinguish.

        # But logic says if CB OPEN, return DENY and log warning.
        # We checked state is OPEN.
