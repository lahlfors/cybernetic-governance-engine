import unittest
from unittest.mock import patch
from financial_advisor.tools.trades import execute_trade, TradeOrder
import uuid
from financial_advisor.safety import safety_filter

class TestGovernanceIntegration(unittest.TestCase):

    def setUp(self):
        # Reset safety filter state to ensure consistent tests
        safety_filter.current_cash = 100000.0

    @patch('financial_advisor.governance.opa_client.evaluate_policy')
    def test_valid_trade_allow(self, mock_evaluate_policy):
        """Test that a valid trade is ALLOWED when OPA approves."""
        # Mock OPA to allow
        mock_evaluate_policy.return_value = "ALLOW"

        # Reduced amount to $5,000 to satisfy CBF velocity constraints (Gamma=0.5)
        # Initial: 100k. Trade: 5k. Next: 95k.
        # h(t)=99k. Req h(t+1)=49.5k. Actual h(t+1)=94k. SAFE.
        amount = 5000.0

        order = TradeOrder(
            transaction_id=str(uuid.uuid4()),
            trader_id="trader_senior",
            trader_role="senior",
            symbol="AAPL",
            amount=amount,
            currency="USD"
        )
        result = execute_trade(order)
        print(f"\n[Valid Trade] Result: {result}")
        self.assertIn("SUCCESS", result)
        self.assertIn(str(amount), result)

    @patch('financial_advisor.governance.opa_client.evaluate_policy')
    def test_trade_blocked_deny(self, mock_evaluate_policy):
        """Test that a trade is BLOCKED when OPA denies."""
        # Mock OPA to deny
        mock_evaluate_policy.return_value = "DENY"

        order = TradeOrder(
             transaction_id=str(uuid.uuid4()),
             trader_id="trader_junior",
             trader_role="junior",
             symbol="GOOG",
             amount=2000000.0,
             currency="USD"
        )
        result = execute_trade(order)
        print(f"\n[Blocked Trade] Result: {result}")
        self.assertIn("BLOCKED", result)
        self.assertIn("Governance Policy Violation", result)

    @patch('financial_advisor.governance.opa_client.evaluate_policy')
    def test_trade_manual_review(self, mock_evaluate_policy):
        """Test that a trade triggers MANUAL REVIEW."""
        # Mock OPA to manual review
        mock_evaluate_policy.return_value = "MANUAL_REVIEW"

        order = TradeOrder(
             transaction_id=str(uuid.uuid4()),
             trader_id="trader_junior",
             trader_role="junior",
             symbol="GOOG",
             amount=8000.0,
             currency="USD"
        )
        result = execute_trade(order)
        print(f"\n[Manual Review Trade] Result: {result}")
        self.assertIn("PENDING_HUMAN_REVIEW", result)
        self.assertIn("Manual Intervention", result)

if __name__ == '__main__':
    unittest.main()
