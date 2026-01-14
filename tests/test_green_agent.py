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

        plan = "Buy 10 shares of TSLA with a limit order and a stop loss at 5%."
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

    # --- Phase 2 Tests (Logic) ---

    def test_logic_high_vol_short_no_hedge(self):
        """Test Phase 2 Logic: Shorting high vol (GME) without hedge."""
        self.mock_opa.evaluate_policy.return_value = "ALLOW"

        # "Short GME" triggers Asset(GME, vol=9.5).
        # "with stop loss" satisfies STPA UCA-1.
        # "GME" does not trigger STPA UCA-2 ("Short Volatility").
        # Logic Rule (HighVolShortHedge) should fire.
        plan = "Short GME with a stop loss."
        result = self.agent.audit_plan(plan)

        self.assertEqual(result.status, "REJECTED")
        self.assertIn("Logic Check Failed", result.feedback)
        self.assertIn("HighVolShortHedge", result.feedback)

    def test_logic_illiquid_market_buy(self):
        """Test Phase 2 Logic: Buying illiquid penny stock."""
        self.mock_opa.evaluate_policy.return_value = "ALLOW"

        # "Buy penny stock" triggers Asset(Penny, liq=2) and Action(Buy).
        # "stop loss" satisfies STPA.
        plan = "Buy penny stock with stop loss."
        result = self.agent.audit_plan(plan)

        self.assertEqual(result.status, "REJECTED")
        self.assertIn("Logic Check Failed", result.feedback)
        self.assertIn("IlliquidMarketOrder", result.feedback)

if __name__ == "__main__":
    unittest.main()
