import unittest
from financial_advisor.tools.trades import execute_trade, TradeOrder

class TestGovernanceIntegration(unittest.TestCase):

    def test_valid_trade(self):
        """Test that a valid trade is ALLOWED by OPA."""
        order = TradeOrder(symbol="AAPL", amount=50000.0, currency="USD")
        result = execute_trade(order)
        print(f"\n[Valid Trade] Result: {result}")
        self.assertIn("SUCCESS", result)
        self.assertIn("50000.0", result)

    def test_high_value_trade_blocked(self):
        """Test that a high-value trade is BLOCKED by OPA policy."""
        # Policy limit is 1,000,000
        order = TradeOrder(symbol="GOOG", amount=2000000.0, currency="USD")
        result = execute_trade(order)
        print(f"\n[High Value Trade] Result: {result}")
        self.assertIn("BLOCKED", result)
        self.assertIn("OPA Policy Violation", result)

    def test_restricted_asset_blocked(self):
        """Test that a restricted asset (BTC) is BLOCKED by OPA policy."""
        order = TradeOrder(symbol="BTC", amount=100.0, currency="BTC")
        result = execute_trade(order)
        print(f"\n[Restricted Asset] Result: {result}")
        self.assertIn("BLOCKED", result)
        self.assertIn("OPA Policy Violation", result)

if __name__ == '__main__':
    unittest.main()
