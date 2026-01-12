"""
Unit Tests for Adapter Node Behavior

Tests the adapter nodes with mocked ADK agent calls to verify:
- Risk analyst parses rejection keywords correctly
- Risk analyst parses approval correctly
- Execution analyst injects feedback when REJECTED_REVISE
"""

import pytest
from unittest.mock import patch, MagicMock


class MockADKResponse:
    """Mock ADK agent response object."""

    def __init__(self, answer: str, function_calls=None):
        self.answer = answer
        self.function_calls = function_calls or []


class TestRiskAnalystNode:
    """Tests for the risk_analyst_node parsing logic."""

    @patch("src.graph.nodes.adapters.run_adk_agent")
    def test_risk_analyst_node_parses_rejection_high_risk(self, mock_run):
        """'high risk' text triggers REJECTED_REVISE status."""
        from src.graph.nodes.adapters import risk_analyst_node

        mock_run.return_value = MockADKResponse(
            "This strategy carries HIGH RISK due to market volatility."
        )
        state = {"messages": [MagicMock(content="Execute 100% portfolio in NVDA")]}

        result = risk_analyst_node(state)

        assert result["risk_status"] == "REJECTED_REVISE"
        assert "HIGH RISK" in result["risk_feedback"]

    @patch("src.graph.nodes.adapters.run_adk_agent")
    def test_risk_analyst_node_parses_rejection_unsafe(self, mock_run):
        """'unsafe' text triggers REJECTED_REVISE status."""
        from src.graph.nodes.adapters import risk_analyst_node

        mock_run.return_value = MockADKResponse(
            "This allocation is UNSAFE and violates diversification rules."
        )
        state = {"messages": [MagicMock(content="All-in on crypto")]}

        result = risk_analyst_node(state)

        assert result["risk_status"] == "REJECTED_REVISE"

    @patch("src.graph.nodes.adapters.run_adk_agent")
    def test_risk_analyst_node_parses_rejection_denied(self, mock_run):
        """'denied' text triggers REJECTED_REVISE status."""
        from src.graph.nodes.adapters import risk_analyst_node

        mock_run.return_value = MockADKResponse("Trade request DENIED.")
        state = {"messages": [MagicMock(content="Margin trade")]}

        result = risk_analyst_node(state)

        assert result["risk_status"] == "REJECTED_REVISE"

    @patch("src.graph.nodes.adapters.run_adk_agent")
    def test_risk_analyst_node_parses_approval(self, mock_run):
        """Clean text without rejection keywords triggers APPROVED status."""
        from src.graph.nodes.adapters import risk_analyst_node

        mock_run.return_value = MockADKResponse(
            "This balanced portfolio allocation meets all risk criteria. "
            "Volatility is within acceptable range. Proceed with execution."
        )
        state = {"messages": [MagicMock(content="60/40 stocks/bonds split")]}

        result = risk_analyst_node(state)

        assert result["risk_status"] == "APPROVED"


class TestExecutionAnalystNode:
    """Tests for the execution_analyst_node feedback injection."""

    @patch("src.graph.nodes.adapters.run_adk_agent")
    def test_execution_analyst_node_normal_flow(self, mock_run):
        """Normal flow without rejection - no feedback injection."""
        from src.graph.nodes.adapters import execution_analyst_node

        mock_run.return_value = MockADKResponse("Strategy: Limit order at $150.")
        state = {
            "messages": [MagicMock(content="Create execution plan for AAPL")],
            "risk_status": "UNKNOWN",
            "risk_feedback": None,
        }

        result = execution_analyst_node(state)

        # Verify the agent was called with original message
        call_args = mock_run.call_args[0]
        assert "CRITICAL" not in call_args[1]
        assert result["risk_status"] == "UNKNOWN"

    @patch("src.graph.nodes.adapters.run_adk_agent")
    def test_execution_analyst_node_injects_feedback(self, mock_run):
        """When REJECTED_REVISE, feedback is injected into the prompt."""
        from src.graph.nodes.adapters import execution_analyst_node

        mock_run.return_value = MockADKResponse("Revised strategy: Reduce position.")
        state = {
            "messages": [MagicMock(content="Original plan")],
            "risk_status": "REJECTED_REVISE",
            "risk_feedback": "Portfolio concentration exceeds 30%.",
        }

        result = execution_analyst_node(state)

        # Verify feedback was injected
        call_args = mock_run.call_args[0]
        assert "CRITICAL" in call_args[1]
        assert "REJECTED by Risk Management" in call_args[1]
        assert "concentration exceeds 30%" in call_args[1]
        # Status should be reset after processing
        assert result["risk_status"] == "UNKNOWN"
