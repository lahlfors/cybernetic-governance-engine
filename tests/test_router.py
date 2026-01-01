import unittest
from unittest.mock import MagicMock, patch
from financial_advisor.tools.router import route_request, RouterIntent
from google.adk.tools.tool_context import ToolContext

class TestRouter(unittest.TestCase):

    @patch("financial_advisor.tools.router.transfer_to_agent")
    def test_routing_market_analysis(self, mock_transfer):
        context = MagicMock(spec=ToolContext)
        result = route_request(RouterIntent.MARKET_ANALYSIS, context)

        mock_transfer.assert_called_with("data_analyst_agent", context)
        self.assertIn("Routing to Data Analyst", result)

    @patch("financial_advisor.tools.router.transfer_to_agent")
    def test_routing_trading_strategy(self, mock_transfer):
        context = MagicMock(spec=ToolContext)
        result = route_request(RouterIntent.TRADING_STRATEGY, context)

        mock_transfer.assert_called_with("governed_trading_agent", context)
        self.assertIn("Routing to Governed Trading Agent", result)

    @patch("financial_advisor.tools.router.transfer_to_agent")
    def test_routing_execution(self, mock_transfer):
        context = MagicMock(spec=ToolContext)
        result = route_request(RouterIntent.EXECUTION_PLAN, context)

        mock_transfer.assert_called_with("execution_analyst_agent", context)
        self.assertIn("Routing to Execution Analyst", result)

    @patch("financial_advisor.tools.router.transfer_to_agent")
    def test_routing_risk(self, mock_transfer):
        context = MagicMock(spec=ToolContext)
        result = route_request(RouterIntent.RISK_ASSESSMENT, context)

        mock_transfer.assert_called_with("risk_analyst_agent", context)
        self.assertIn("Routing to Risk Analyst", result)

if __name__ == '__main__':
    unittest.main()
