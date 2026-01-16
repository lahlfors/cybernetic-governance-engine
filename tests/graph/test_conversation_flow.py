import pytest
from unittest.mock import patch, MagicMock
from src.graph.graph import create_graph
from langchain_core.messages import HumanMessage
from src.graph.nodes.adapters import AgentResponse

@pytest.fixture
def graph():
    return create_graph()

@patch('src.graph.nodes.supervisor_node.run_adk_agent')
def test_supervisor_updates_state_and_augments_message(mock_run_adk_agent, graph):
    """
    Tests that the supervisor node correctly parses the user's message,
    updates the AgentState with the risk profile, and calls the agent
    with a correctly augmented message.
    """
    # Mock the agent response to prevent actual API calls
    mock_run_adk_agent.return_value = AgentResponse(answer="Proceeding with strategy.")

    thread = {"configurable": {"thread_id": "state-update-thread"}}

    # 1. Initial message (no profile)
    graph.invoke({"messages": [HumanMessage(content="research nvda")]}, thread)

    # 2. User provides their profile
    final_state = graph.invoke(
        {"messages": [HumanMessage(content="I am a conservative investor with a short-term horizon.")]},
        thread
    )

    # --- Assertions ---
    # 1. Verify that the AgentState was updated correctly
    assert final_state['risk_attitude'] == 'conservative', "Risk attitude was not updated in the state."
    assert final_state['investment_period'] == 'short-term', "Investment period was not updated in the state."

    # 2. Verify that the agent was called with the augmented message
    # The last call to the mock contains the arguments it was called with.
    last_call_args = mock_run_adk_agent.call_args
    augmented_message = last_call_args[0][1] # The 'augmented_message' is the second argument

    assert "User Profile Context:" in augmented_message
    assert "- Risk Attitude: conservative" in augmented_message
    assert "- Investment Period: short-term" in augmented_message
    assert "User Request: i am a conservative investor with a short-term horizon." in augmented_message
