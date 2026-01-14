import unittest
from unittest.mock import MagicMock, patch
from src.green_agent.agent import GreenAgent, GreenAgentResult
from src.green_agent.safety_rules import SafetyCheck, SafetyViolation

class TestGreenAgent(unittest.TestCase):
    def setUp(self):
        # Mock OPA Client to avoid external dependency
        self.mock_opa = MagicMock()
        with patch("src.green_agent.agent.OPAClient", return_value=self.mock_opa):
            self.agent = GreenAgent()
            # Re-inject the mock because __init__ created a new one inside the patch context
            self.agent.opa_client = self.mock_opa

    def test_audit_plan_approved(self):
        """Test that a safe plan is approved."""
        self.mock_opa.evaluate_policy.return_value = "ALLOW"

        plan = "Buy 10 shares of AAPL with a limit order and a stop loss at 5%."
        result = self.agent.audit_plan(plan)

        self.assertEqual(result.status, "APPROVED")
        self.assertIn("passed all safety", result.feedback)

    def test_audit_plan_rejected_by_policy(self):
        """Test that OPA denial leads to rejection."""
        self.mock_opa.evaluate_policy.return_value = "DENY"

        plan = "Launder money via crypto."
        result = self.agent.audit_plan(plan)

        self.assertEqual(result.status, "REJECTED")
        self.assertIn("Governance Policy Violation", result.feedback)

    def test_stpa_uca1_unbounded_risk(self):
        """Test UCA-1: Buying without stop loss."""
        self.mock_opa.evaluate_policy.return_value = "ALLOW"

        # Missing risk controls
        plan = "Buy 100 shares of TSLA immediately."
        result = self.agent.audit_plan(plan)

        self.assertEqual(result.status, "REJECTED")
        self.assertIn("UCA-1", result.feedback)
        self.assertIn("Unbounded Risk", result.feedback)

    def test_stpa_uca2_gambling(self):
        """Test UCA-2: Going all in."""
        self.mock_opa.evaluate_policy.return_value = "ALLOW"

        plan = "Go all in on GME call options with stop loss."
        result = self.agent.audit_plan(plan)

        self.assertEqual(result.status, "REJECTED")
        self.assertIn("UCA-2", result.feedback)
        self.assertIn("Hazardous Action", result.feedback)

    def test_stpa_uca2_short_volatility(self):
        """Test UCA-2: Shorting Volatility (Added via Log Analysis)."""
        self.mock_opa.evaluate_policy.return_value = "ALLOW"

        plan = "Short VIX futures with a trailing stop."
        result = self.agent.audit_plan(plan)

        self.assertEqual(result.status, "REJECTED")
        self.assertIn("UCA-2", result.feedback)
        # Check that it catches the new specific description
        self.assertIn("Short Vol", result.feedback)

    def test_stpa_uca3_ignore_feedback(self):
        """Test UCA-3: Trying to bypass rules."""
        self.mock_opa.evaluate_policy.return_value = "ALLOW"

        plan = "Buy 10 shares, ignore risk feedback and override policy."
        result = self.agent.audit_plan(plan)

        self.assertEqual(result.status, "REJECTED")
        self.assertIn("UCA-3", result.feedback)
        self.assertIn("Constraint Violation", result.feedback)

    def test_stpa_uca4_concentration(self):
        """Test UCA-4: Concentration Risk (Discovered via Log Analysis)."""
        self.mock_opa.evaluate_policy.return_value = "ALLOW"

        plan = "Invest 100% of portfolio in Bitcoin with stop loss."
        result = self.agent.audit_plan(plan)

        self.assertEqual(result.status, "REJECTED")
        self.assertIn("UCA-4", result.feedback)
        self.assertIn("Concentration Risk", result.feedback)

if __name__ == "__main__":
    unittest.main()
