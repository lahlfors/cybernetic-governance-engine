import unittest
from unittest.mock import patch
from financial_advisor.tools.trades import execute_trade, TradeOrder

class TestGovernanceIntegration(unittest.TestCase):

    @patch('financial_advisor.governance.opa_client.check_policy')
    def test_valid_trade(self, mock_check_policy):
        """Test that a valid trade is ALLOWED when OPA approves."""
        # Mock OPA to allow
        mock_check_policy.return_value = True

        order = TradeOrder(symbol="AAPL", amount=50000.0, currency="USD")
        result = execute_trade(order)
        print(f"\n[Valid Trade] Result: {result}")
        self.assertIn("SUCCESS", result)
        self.assertIn("50000.0", result)

    @patch('financial_advisor.governance.opa_client.check_policy')
    def test_high_value_trade_blocked(self, mock_check_policy):
        """Test that a trade is BLOCKED when OPA denies."""
        # Mock OPA to deny
        mock_check_policy.return_value = False

        order = TradeOrder(symbol="GOOG", amount=2000000.0, currency="USD")
        result = execute_trade(order)
        print(f"\n[High Value Trade] Result: {result}")
        self.assertIn("BLOCKED", result)
        self.assertIn("Governance Policy Violation", result)

if __name__ == '__main__':
    unittest.main()
