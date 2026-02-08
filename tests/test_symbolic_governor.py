import pytest
from unittest.mock import AsyncMock, Mock

from src.gateway.governance import SymbolicGovernor, GovernanceError

@pytest.mark.asyncio
async def test_symbolic_governor_confidence_pass():
    opa_client = AsyncMock()
    opa_client.evaluate_policy.return_value = "ALLOW"

    safety_filter = Mock()
    safety_filter.verify_action.return_value = "SAFE"

    consensus_engine = AsyncMock()
    consensus_engine.check_consensus.return_value = {"status": "APPROVE"}

    governor = SymbolicGovernor(opa_client, safety_filter, consensus_engine)

    # Confidence >= 0.95
    params = {"confidence": 0.99, "amount": 100, "symbol": "AAPL"}
    await governor.govern("execute_trade", params)

    # Should not raise exception

@pytest.mark.asyncio
async def test_symbolic_governor_confidence_fail():
    opa_client = AsyncMock()
    safety_filter = Mock()
    consensus_engine = AsyncMock()

    governor = SymbolicGovernor(opa_client, safety_filter, consensus_engine)

    # Confidence < 0.95
    params = {"confidence": 0.94, "amount": 100, "symbol": "AAPL"}

    with pytest.raises(GovernanceError) as excinfo:
        await governor.govern("execute_trade", params)

    assert "Confidence" in str(excinfo.value)
    assert "SR 11-7 Violation" in str(excinfo.value)

@pytest.mark.asyncio
async def test_symbolic_governor_opa_fail():
    opa_client = AsyncMock()
    opa_client.evaluate_policy.return_value = "DENY"

    safety_filter = Mock()
    safety_filter.verify_action.return_value = "SAFE"

    consensus_engine = AsyncMock()

    governor = SymbolicGovernor(opa_client, safety_filter, consensus_engine)

    params = {"confidence": 0.99, "amount": 100}

    with pytest.raises(GovernanceError) as excinfo:
        await governor.govern("execute_trade", params)

    assert "ISO 42001 Policy Violation" in str(excinfo.value)

@pytest.mark.asyncio
async def test_symbolic_governor_cbf_fail():
    opa_client = AsyncMock()
    opa_client.evaluate_policy.return_value = "ALLOW"

    safety_filter = Mock()
    safety_filter.verify_action.return_value = "UNSAFE: Bankruptcy"

    consensus_engine = AsyncMock()

    governor = SymbolicGovernor(opa_client, safety_filter, consensus_engine)

    params = {"confidence": 0.99, "amount": 100}

    with pytest.raises(GovernanceError) as excinfo:
        await governor.govern("execute_trade", params)

    assert "Safety Violation (CBF)" in str(excinfo.value)

@pytest.mark.asyncio
async def test_symbolic_governor_consensus_fail():
    opa_client = AsyncMock()
    opa_client.evaluate_policy.return_value = "ALLOW"

    safety_filter = Mock()
    safety_filter.verify_action.return_value = "SAFE"

    consensus_engine = AsyncMock()
    consensus_engine.check_consensus.return_value = {"status": "REJECT", "reason": "Too risky"}

    governor = SymbolicGovernor(opa_client, safety_filter, consensus_engine)

    params = {"confidence": 0.99, "amount": 100, "symbol": "XYZ"}

    with pytest.raises(GovernanceError) as excinfo:
        await governor.govern("execute_trade", params)

    assert "Consensus Rejection" in str(excinfo.value)
