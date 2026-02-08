# tests/verify_orchestrator.py

import sys
import os
import asyncio
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.governed_financial_advisor.orchestrator import FinancialAdvisorOrchestrator

# Mock Nodes to avoid external dependencies during orchestration test
@patch("src.governed_financial_advisor.orchestrator.supervisor_node")
@patch("src.governed_financial_advisor.orchestrator.data_analyst_node")
@patch("src.governed_financial_advisor.orchestrator.execution_analyst_node")
@patch("src.governed_financial_advisor.orchestrator.evaluator_node")
@patch("src.governed_financial_advisor.orchestrator.governed_trader_node")
@patch("src.governed_financial_advisor.orchestrator.explainer_node")
def test_simulation_flow(mock_explainer, mock_trader, mock_evaluator, mock_planner, mock_data, mock_supervisor):
    print("--- Testing Orchestrator Flow (Supervisor -> Planner -> Evaluator -> Trader -> Explainer) ---")

    # Setup Mocks
    mock_supervisor.return_value = {"next_step": "execution_analyst", "messages": [("ai", "I'll plan a trade.")]}
    mock_planner.return_value = {"messages": [("ai", "Plan: Buy AAPL.")], "execution_plan_output": {"steps": [{"action": "buy"}]}}

    # Evaluator is async
    async def mock_eval_async(state):
        return {"next_step": "governed_trader", "evaluation_result": {"verdict": "APPROVED"}}
    mock_evaluator.side_effect = mock_eval_async

    mock_trader.return_value = {"messages": [("ai", "Trade executed.")]}

    # Explainer is async
    async def mock_explain_async(state):
        return {"next_step": "FINISH", "messages": [("ai", "Here is the report.")]}
    mock_explainer.side_effect = mock_explain_async

    # Run
    orchestrator = FinancialAdvisorOrchestrator()
    final_state = orchestrator.run("Buy AAPL stock")

    # Verify
    print("Final State Keys:", final_state.keys())
    print("Final Messages:", len(final_state["messages"]))

    # Check Logic
    assert final_state["next_step"] == "FINISH"
    assert len(final_state["messages"]) >= 5 # User + Sup + Plan + Trad + Explain

    print("✅ Orchestrator Flow Verification Passed!")

if __name__ == "__main__":
    test_simulation_flow()
