import pytest
import responses
from src.graph.hybrid_graph import create_hybrid_graph

@pytest.fixture
def mock_opa():
    with responses.RequestsMock() as rsps:
        yield rsps

def test_hybrid_flow_allow(mock_opa):
    graph = create_hybrid_graph()

    # 1. Mock OPA ALLOW
    mock_opa.add(
        responses.POST,
        "http://localhost:8181/v1/data/banking/governance",
        json={"result": {"analysis": {"status": "ALLOW", "reason": "Safe Harbor"}}},
        status=200
    )

    state = {
        "proposed_action": "transfer",
        "context": {"amount": 100, "risk_score": 0.0}
    }

    result = graph.invoke(state)

    assert result["final_outcome"] == "EXECUTED"
    assert result["governance_result"]["status"] == "ALLOW"

def test_hybrid_flow_deny(mock_opa):
    graph = create_hybrid_graph()

    # 1. Mock OPA DENY
    mock_opa.add(
        responses.POST,
        "http://localhost:8181/v1/data/banking/governance",
        json={"result": {"analysis": {"status": "DENY", "reason": "Explicit Rule"}}},
        status=200
    )

    state = {
        "proposed_action": "transfer",
        "context": {"amount": 99999, "risk_score": 0.9}
    }

    result = graph.invoke(state)

    assert result["final_outcome"] == "BLOCKED"
    assert result["governance_result"]["status"] == "DENY"

def test_hybrid_flow_uncertain(mock_opa):
    """
    Test the Fallback: OPA is Uncertain -> System 2 Runs -> Updates Result
    """
    graph = create_hybrid_graph()

    # 1. Mock OPA UNCERTAIN
    mock_opa.add(
        responses.POST,
        "http://localhost:8181/v1/data/banking/governance",
        json={"result": {"analysis": {"status": "UNCERTAIN", "reason": "No rule"}}},
        status=200
    )

    # Context that will pass System 2 (Low Tenure, Block Action)
    # Block on low tenure -> Low Churn -> ALLOW
    state = {
        "proposed_action": "block_transaction",
        "context": {
            "Transaction_Amount": 100.0,
            "Location_Mismatch": 0,
            "Fraud_Risk": 0.4, # Slightly lower risk to reduce baseline friction
            "Tenure_Years": 0.0 # Zero tenure = Minimal interaction effect
        }
    }

    print("\n--- Testing Hybrid Fallback ---")
    result = graph.invoke(state)

    print("Final Result:", result)

    assert result["final_outcome"] == "EXECUTED" # Should eventually allow
    assert "System 2 Simulation" in result["governance_result"]["reason"]

if __name__ == "__main__":
    pass
