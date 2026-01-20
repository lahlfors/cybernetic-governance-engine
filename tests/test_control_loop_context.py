import pytest
from src.graph.state import AgentState
from src.graph.nodes.supervisor_node import supervisor_node
from src.graph.nodes.safety_node import safety_check_node
from src.governance.stpa import ControlLoop
from unittest.mock import MagicMock, patch

# Mock responses for the supervisor
@patch("src.graph.nodes.supervisor_node.run_adk_agent")
def test_supervisor_initializes_stpa_context(mock_run_agent):
    """
    Test that the supervisor node correctly initializes the ControlLoop metadata
    when routing to a critical component (e.g., Governed Trader).
    """
    # Setup Mock Response that triggers a trade
    mock_response = MagicMock()
    mock_response.answer = "Initiating trade."

    # Correctly configure the function call mock
    func_call = MagicMock()
    func_call.name = "route_request"
    func_call.args = {"target": "trade"}

    mock_response.function_calls = [func_call]
    mock_run_agent.return_value = mock_response

    # Initial State
    state = {
        "messages": [("user", "Buy 100 AAPL")],
        "risk_attitude": "moderate",
        "investment_period": "long-term",
        "next_step": "FINISH",
        "risk_status": "UNKNOWN",
        "risk_feedback": None,
        "control_loop_metadata": None,
        "execution_plan_output": None,
        "user_id": "test_user"
    }

    # Run Node
    result = supervisor_node(state)

    # Assertions
    assert result["next_step"] == "governed_trader"
    assert "control_loop_metadata" in result

    stpa_meta = result["control_loop_metadata"]
    assert isinstance(stpa_meta, ControlLoop)
    assert stpa_meta.id == "LOOP-TRADE-001"
    assert stpa_meta.controller == "GovernedTrader"
    assert "execute_order" in stpa_meta.control_actions

@patch("src.graph.nodes.safety_node.opa_client")
def test_safety_node_uses_stpa_context(mock_opa_client):
    """
    Test that the Safety Node extracts the STPA metadata and passes it to OPA.
    """
    # Setup Mock OPA
    mock_opa_client.evaluate_policy.return_value = "ALLOW"

    # Setup STPA Context
    stpa_meta = ControlLoop(
        id="LOOP-TEST",
        name="Test Loop",
        controller="TestController",
        controlled_process="TestProcess",
        control_actions=["test_action"],
        feedback_mechanism="None"
    )

    # State with Plan and Context
    state = {
        "execution_plan_output": {"action": "test_action", "amount": 100, "symbol": "TEST"},
        "control_loop_metadata": stpa_meta,
        "user_id": "test_user",
        "risk_attitude": "conservative",
        "messages": [],
        "next_step": "governed_trader",
        "risk_status": "APPROVED",
        "risk_feedback": None,
        "investment_period": "short-term"
    }

    # Run Node
    safety_check_node(state)

    # Assertions
    mock_opa_client.evaluate_policy.assert_called_once()
    call_args = mock_opa_client.evaluate_policy.call_args[0][0]

    assert "stpa_context" in call_args
    assert call_args["stpa_context"]["loop_id"] == "LOOP-TEST"
    assert call_args["stpa_context"]["controller"] == "TestController"
