import unittest
from unittest.mock import MagicMock, patch
from financial_advisor.green_agent.agent import GreenAgentService, RiskPacket

class TestGreenAgent(unittest.TestCase):
    def setUp(self):
        self.service = GreenAgentService()
        # Mock the constitution to always allow, so we can test simulation logic isolation
        self.service.constitution.check_action = MagicMock(return_value=MagicMock(allowed=True))

    def test_simulation_safe_trade(self):
        # Trade of 50k (Balance 100k) -> Safe
        payload = {"amount": 50000, "symbol": "AAPL", "action": "buy"}
        result = self.service.simulate_outcome("execute_trade", payload)

        self.assertTrue(result.safe)
        self.assertEqual(result.projected_balance, 50000.0)

    def test_simulation_unsafe_trade(self):
        # Trade of 150k (Balance 100k) -> Unsafe
        payload = {"amount": 150000, "symbol": "AAPL", "action": "buy"}
        result = self.service.simulate_outcome("execute_trade", payload)

        self.assertFalse(result.safe)
        self.assertIn("Insolvency Risk", result.violation_reason)

    @patch('financial_advisor.green_agent.agent.original_execute_trade')
    def test_verify_and_execute_blocks_unsafe(self, mock_execute):
        # Attempt unsafe trade
        payload = {"amount": 150000, "symbol": "AAPL", "action": "buy", "transaction_id": "123", "trader_id": "1", "trader_role": "junior"}
        response = self.service.verify_and_execute("execute_trade", payload)

        # Should return blocked message
        self.assertIn("BLOCKED by Green Agent Simulation", response)
        # Should NOT call the underlying tool
        mock_execute.assert_not_called()

    @patch('financial_advisor.green_agent.agent.original_execute_trade')
    def test_verify_and_execute_allows_safe(self, mock_execute):
        # Attempt safe trade
        payload = {"amount": 10000, "symbol": "AAPL", "action": "buy", "transaction_id": "123", "trader_id": "1", "trader_role": "junior"}
        mock_execute.return_value = "Trade Executed"

        response = self.service.verify_and_execute("execute_trade", payload)

        mock_execute.assert_called_once()
        self.assertEqual(response, "Trade Executed")

if __name__ == '__main__':
    unittest.main()
