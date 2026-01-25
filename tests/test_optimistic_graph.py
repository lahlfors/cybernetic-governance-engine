from langgraph.graph.state import CompiledStateGraph

from src.graph.graph import create_graph


def test_graph_compilation():
    # Use a mock Redis URL or None if checkpointer allows
    graph = create_graph(redis_url="redis://localhost:6379")
    assert isinstance(graph, CompiledStateGraph)

def test_graph_nodes_exist():
    graph = create_graph()
    # Accessing the underlying graph structure
    nodes = graph.get_graph().nodes
    assert "optimistic_execution" in nodes
    assert "supervisor" in nodes
    assert "safety_check" not in nodes # Should be removed/replaced

def test_optimistic_execution_node_logic():
    # Unit test the node logic directly
    from unittest.mock import patch

    from src.graph.nodes.optimistic_nodes import (
        optimistic_execution_node,
    )

    mock_state = {"execution_plan_output": {"symbol": "AAPL"}}

    # Mock the internal calls to safety_check_node and trader_prep_node
    # We need to patch the imported functions in optimistic_nodes module
    with patch("src.graph.nodes.optimistic_nodes.safety_check_node") as mock_safety:
        with patch("src.graph.nodes.optimistic_nodes.trader_prep_node") as mock_prep:
            mock_safety.return_value = {"safety_status": "APPROVED"}
            mock_prep.return_value = {"trader_prep_output": {"symbol": "AAPL"}}

            result = optimistic_execution_node(mock_state)

            assert result["safety_status"] == "APPROVED"
            assert result["trader_prep_output"]["symbol"] == "AAPL"

def test_router_logic():
    from src.graph.nodes.optimistic_nodes import route_optimistic_execution

    assert route_optimistic_execution({"safety_status": "APPROVED"}) == "governed_trader"
    assert route_optimistic_execution({"safety_status": "SKIPPED"}) == "governed_trader"
    assert route_optimistic_execution({"safety_status": "BLOCKED"}) == "execution_analyst"
    assert route_optimistic_execution({"safety_status": "ESCALATED"}) == "execution_analyst"
