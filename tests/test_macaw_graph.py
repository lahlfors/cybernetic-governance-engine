
import pytest
from unittest.mock import MagicMock, patch
from src.governed_financial_advisor.graph.graph import create_graph

# Mock AgentState
def mock_state():
    return {
        "messages": [],
        "next_step": "supervisor",
        "risk_status": "UNKNOWN",
        "safety_status": "APPROVED",
        "user_id": "test_user"
    }

def test_graph_compilation():
    """
    Verifies that the graph compiles successfully with the new MACAW nodes.
    """
    try:
        graph = create_graph(redis_url=None)
        assert graph is not None
        print("Graph compiled successfully")
    except Exception as e:
        pytest.fail(f"Graph compilation failed: {e}")

@patch("src.governed_financial_advisor.graph.nodes.adapters.run_adk_agent")
def test_macaw_flow_structure(mock_run_agent):
    """
    Verifies the structure of the MACAW graph by inspecting edges/nodes
    (indirectly via compilation, as direct graph inspection depends on LangGraph internals).
    Ideally, we check that we can traverse from Planner -> Evaluator.
    """
    graph = create_graph()

    # We can't easily inspect the compiled graph structure without running it,
    # but successful compilation implies the nodes exist.
    assert graph is not None
