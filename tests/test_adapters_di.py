import pytest
from unittest.mock import MagicMock
from src.graph.nodes.adapters import get_agent, inject_agent, clear_agent_cache, data_analyst_node

@pytest.fixture(autouse=True)
def clean_di():
    clear_agent_cache()
    yield
    clear_agent_cache()

def test_dependency_injection():
    # Define a mock agent
    mock_agent = MagicMock()
    mock_agent.run.return_value = [] # Simulate ADK runner output?
    # ADK runner.run returns events.

    # But run_adk_agent calls runner.run.
    # We are testing get_agent mostly.

    # 1. Inject mock
    inject_agent("data_analyst", mock_agent)

    # 2. Retrieve
    retrieved = get_agent("data_analyst", lambda: "Not Used")

    assert retrieved == mock_agent

def test_data_analyst_node_uses_mock():
    # Mock the agent to return a specific response to verify interaction
    mock_agent = MagicMock()
    # Mock Runner interactions if possible, but run_adk_agent instantiates Runner(agent=...)
    # So we are mocking the agent instance passed to Runner.
    # The Runner will use this agent.

    # Ideally we'd mock run_adk_agent to avoid complex ADK mocking,
    # but here we test the DI integration in the node.

    # If we inject a mock agent, data_analyst_node should retrieve it.
    inject_agent("data_analyst", mock_agent)

    # To avoid running actual ADK logic which requires auth etc, we might mock run_adk_agent.
    # But adapters.py imports run_adk_agent from itself (it defines it).

    # We can patch `src.graph.nodes.adapters.run_adk_agent`
    with pytest.MonkeyPatch.context() as mp:
        mock_run = MagicMock()
        mock_run.return_value.answer = "Mocked Analysis"
        mp.setattr("src.graph.nodes.adapters.run_adk_agent", mock_run)

        state = {"messages": [MagicMock(content="Analyze AAPL")]}
        result = data_analyst_node(state)

        # Verify run_adk_agent was called with our mock_agent
        mock_run.assert_called_once()
        args, _ = mock_run.call_args
        assert args[0] == mock_agent
        assert result["messages"][0][1] == "Data Analysis: Mocked Analysis"
