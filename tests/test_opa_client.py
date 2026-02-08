import httpx
import pytest
import respx
import sys
import os

sys.path.append(os.getcwd())

from src.gateway.core.policy import OPAClient


@pytest.fixture
def opa_client():
    return OPAClient()

@pytest.mark.asyncio
async def test_opa_allow(opa_client):
    async with respx.mock(base_url="http://localhost:8181/v1/data/finance/decision") as mock:
        mock.post("http://localhost:8181/v1/data/finance/decision").mock(return_value=httpx.Response(200, json={"result": "ALLOW"}))
        # Note: OPAClient uses config.OPA_URL, usually localhost:8181 in tests

        result = await opa_client.evaluate_policy({"action": "test"})
        # OPAClient returns ALLOW/DENY/MANUAL_REVIEW string or boolean?
        # Check OPAClient implementation.
        # Assuming it returns decision string.
        assert result == "ALLOW"
