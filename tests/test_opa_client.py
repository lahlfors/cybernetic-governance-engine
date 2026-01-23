import pytest
import requests
import responses
from src.governance.engine import PolicyEngine

@pytest.fixture
def mock_opa():
    with responses.RequestsMock() as rsps:
        yield rsps

def test_opa_allow(mock_opa):
    engine = PolicyEngine(policy_url="http://localhost:8181/v1/data/banking/governance")

    # Mock OPA Response for ALLOW
    mock_opa.add(
        responses.POST,
        "http://localhost:8181/v1/data/banking/governance",
        json={"result": {"allow": True}},
        status=200
    )

    input_data = {
        "action": "transfer",
        "context": {"amount": 500, "risk_score": 0.1}
    }

    result = engine.evaluate(input_data)
    assert result["status"] == "ALLOW"
    assert len(mock_opa.calls) == 1

def test_opa_deny(mock_opa):
    engine = PolicyEngine(policy_url="http://localhost:8181/v1/data/banking/governance")

    # Mock OPA Response for DENY
    mock_opa.add(
        responses.POST,
        "http://localhost:8181/v1/data/banking/governance",
        json={"result": {"allow": False}},
        status=200
    )

    input_data = {
        "action": "transfer",
        "context": {"amount": 50000, "risk_score": 0.1}
    }

    result = engine.evaluate(input_data)
    assert result["status"] == "DENY"
    assert "Policy Violation" in result["reason"]

def test_opa_connection_failure(mock_opa):
    engine = PolicyEngine(policy_url="http://localhost:8181/v1/data/banking/governance")

    # Mock Connection Error
    mock_opa.add(
        responses.POST,
        "http://localhost:8181/v1/data/banking/governance",
        body=Exception("Connection refused")
    )

    input_data = {"action": "test"}
    result = engine.evaluate(input_data)

    assert result["status"] == "DENY"
    assert "Communication Failure" in result["reason"]

if __name__ == "__main__":
    # If run directly
    pass
