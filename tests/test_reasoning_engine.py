
import pytest
from unittest.mock import MagicMock, patch
from src.governed_financial_advisor.reasoning_engine import FinancialAdvisorEngine

# Patch the Orchestrator class at its SOURCE
@patch("src.governed_financial_advisor.orchestrator.FinancialAdvisorOrchestrator")
def test_reasoning_engine_initialization(MockOrchestrator):
    """
    Test that FinancialAdvisorEngine initializes correctly.
    """
    engine = FinancialAdvisorEngine(project="test-project", location="us-central1")

    # set_up() should initialize the orchestrator
    engine.set_up()

    assert engine.project == "test-project"
    assert engine.orchestrator is not None
    MockOrchestrator.assert_called_once()

@patch("src.governed_financial_advisor.orchestrator.FinancialAdvisorOrchestrator")
def test_reasoning_engine_query(MockOrchestrator):
    """
    Test that query() method invokes the orchestrator and returns correct format.
    """
    mock_orch_instance = MockOrchestrator.return_value

    # Mock return value of orchestrator.run()
    # It returns 'state' dict
    mock_state = {
        "messages": [
            MagicMock(content="Final response")
        ],
        "execution_plan_output": {"steps": ["step1"]},
        "execution_result": {"status": "success"},
        "evaluation_result": {"safe": True}
    }
    mock_orch_instance.run.return_value = mock_state

    engine = FinancialAdvisorEngine()
    engine.set_up() # Initialize orchestrator

    response = engine.query(prompt="Analyze GOOG")

    assert response["response"] == "Final response"
    assert "Final response" in response["response"]

    mock_orch_instance.run.assert_called_once()
