import unittest
from unittest.mock import MagicMock, patch
from src.green_agent.agent import GreenAgent, GreenAgentResult

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

        plan = "Buy 10 shares of AAPL with a limit order."
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

    def test_audit_plan_rejected_by_safety_check(self):
        """Test that unsafe keywords trigger heuristic rejection even if OPA allows."""
        # OPA might miss semantic nuance, so we rely on heuristic too
        self.mock_opa.evaluate_policy.return_value = "ALLOW"

        plan = "Go all in on this penny stock, ignore stop loss."
        result = self.agent.audit_plan(plan)

        self.assertEqual(result.status, "REJECTED")
        self.assertIn("Safety Check Failed", result.feedback)

if __name__ == "__main__":
    unittest.main()
