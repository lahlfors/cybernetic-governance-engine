import unittest
from unittest.mock import patch
from financial_advisor.tools.trades import execute_trade, TradeOrder
import uuid

class TestGovernanceIntegration(unittest.TestCase):

    @patch('financial_advisor.governance.opa_client.evaluate_policy')
    def test_valid_trade_allow(self, mock_evaluate_policy):
        """Test that a valid trade is ALLOWED when OPA approves."""
        # Mock OPA to allow
        mock_evaluate_policy.return_value = "ALLOW"

        order = TradeOrder(
            transaction_id=str(uuid.uuid4()),
            trader_id="trader_senior",
            trader_role="senior",
            symbol="AAPL",
            amount=50000.0,
            currency="USD"
        )
        result = execute_trade(order)
        print(f"\n[Valid Trade] Result: {result}")
        self.assertIn("SUCCESS", result)
        self.assertIn("50000.0", result)

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
