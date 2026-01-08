import pytest
from unittest.mock import MagicMock, patch
from financial_advisor.state import AgentState
from financial_advisor.nodes.supervisor_node import supervisor_node, RouteDecision

def test_supervisor_node_routing():
    """
    Test that the supervisor correctly routes based on LLM output.
    We mock the ChatGoogleGenerativeAI to avoid actual API calls.
    """
    mock_llm = MagicMock()
    mock_structured_llm = MagicMock()

    # Setup mock chain
    mock_llm.with_structured_output.return_value = mock_structured_llm

    # Case 1: Route to Data Analyst
    mock_structured_llm.invoke.return_value = RouteDecision(next="data_analyst")

    state = {"messages": [("user", "Analyze AAPL stock")]}

    # Patch the class instantiation inside the node
    with patch("financial_advisor.nodes.supervisor_node.ChatGoogleGenerativeAI", return_value=mock_llm):
        result = supervisor_node(state)

    assert result["next_step"] == "data_analyst"

def test_supervisor_node_finish():
    """
    Test routing to FINISH.
    """
    mock_llm = MagicMock()
    mock_structured_llm = MagicMock()

    mock_llm.with_structured_output.return_value = mock_structured_llm
    mock_structured_llm.invoke.return_value = RouteDecision(next="FINISH")

    state = {"messages": [("user", "Thanks, goodbye")]}

    with patch("financial_advisor.nodes.supervisor_node.ChatGoogleGenerativeAI", return_value=mock_llm):
        result = supervisor_node(state)

    assert result["next_step"] == "FINISH"
