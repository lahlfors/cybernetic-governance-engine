import pytest
from unittest.mock import MagicMock, patch
from financial_advisor.nodes.adapters import (
    data_analyst_node,
    risk_analyst_node,
    execution_analyst_node,
    governed_trader_node,
    run_adk_agent
)

# Mock state
mock_state = {"messages": [("user", "Test input")]}

@patch("financial_advisor.nodes.adapters.Runner")
def test_run_adk_agent_wrapper(mock_runner_cls):
    """
    Test the generic adapter wrapper.
    """
    # Setup mock runner instance
    mock_runner_instance = MagicMock()
    mock_runner_cls.return_value = mock_runner_instance

    # Setup mock response
    mock_response = MagicMock()
    mock_response.answer = "Agent response text"
    mock_runner_instance.run.return_value = mock_response

    # Dummy agent instance (can be anything since we mock Runner)
    dummy_agent = MagicMock()

    result = run_adk_agent(dummy_agent, mock_state, prefix="Prefix: ")

    # Verification
    mock_runner_cls.assert_called_once()
    mock_runner_instance.run.assert_called_once_with(session_id="default", query="Test input")
    assert result["messages"][0][1] == "Prefix: Agent response text"

@patch("financial_advisor.nodes.adapters.run_adk_agent")
def test_risk_analyst_node_logic_approved(mock_run_adapter):
    """
    Test that risk analyst node parses 'APPROVED' logic.
    """
    # Mock return from adapter
    mock_run_adapter.return_value = {"messages": [("ai", "Risk Analysis: APPROVED. Low risk.")]}

    result = risk_analyst_node(mock_state)

    assert result["risk_status"] == "APPROVED"
    assert "APPROVED" in result["messages"][0][1]

@patch("financial_advisor.nodes.adapters.run_adk_agent")
def test_risk_analyst_node_logic_rejected(mock_run_adapter):
    """
    Test that risk analyst node parses 'REJECT' logic.
    """
    # Mock return from adapter
    mock_run_adapter.return_value = {"messages": [("ai", "Risk Analysis: REJECT. High risk detected.")]}

    result = risk_analyst_node(mock_state)

    assert result["risk_status"] == "REJECTED_REVISE"
    assert "REJECT" in result["messages"][0][1]
