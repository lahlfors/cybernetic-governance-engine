import unittest
from unittest.mock import MagicMock
from financial_advisor.governance.constitution import Constitution
from financial_advisor.governance.opa_reasoner import OPAReasoner
from financial_advisor.governance_init import OPAClient

class TestConstitution(unittest.TestCase):
    def setUp(self):
        # Mock the OPAClient
        self.mock_client = MagicMock(spec=OPAClient)
        self.reasoner = OPAReasoner(client=self.mock_client)
        self.constitution = Constitution(reasoner=self.reasoner)

    def test_allow_action(self):
        self.mock_client.evaluate_policy.return_value = "ALLOW"
        context = {"action": "test_action", "amount": 100}

        result = self.constitution.check_action("test_action", context)

        self.assertTrue(result.allowed)
        self.assertEqual(result.reason, "OPA Policy Allowed")
        self.mock_client.evaluate_policy.assert_called_with(context)

    def test_deny_action(self):
        self.mock_client.evaluate_policy.return_value = "DENY"
        context = {"action": "risky_action", "amount": 1000000}

        result = self.constitution.check_action("risky_action", context)

        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, "OPA Policy Denied")

    def test_manual_review_action(self):
        self.mock_client.evaluate_policy.return_value = "MANUAL_REVIEW"
        context = {"action": "borderline_action"}

        result = self.constitution.check_action("borderline_action", context)

        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, "Manual Review Required (Constructive Friction)")

if __name__ == '__main__':
    unittest.main()
