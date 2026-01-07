import unittest
from unittest.mock import MagicMock
from financial_advisor.governance.autopt import GovernanceLoop, StaticRedTeam, LoggerBlueTeam

class TestAutoPT(unittest.TestCase):
    def setUp(self):
        self.red_team = StaticRedTeam()
        self.blue_team = LoggerBlueTeam()
        # Mock the agent runner
        self.mock_runner = MagicMock()
        self.loop = GovernanceLoop(self.mock_runner, self.red_team, self.blue_team)

    def test_cycle_defended(self):
        # Simulate agent blocking everything
        self.mock_runner.return_value = "BLOCKED: Policy Violation"

        # Spy on the blue team log (we can't easily mock the logger, so we check if analyze_failure ran without error)
        # Real verification would check logs or mocked logger calls.
        with self.assertLogs("AutoPT", level="INFO") as cm:
            self.loop.run_cycle()
            self.assertTrue(any("Attack Defended" in log for log in cm.output))

    def test_cycle_successful_attack(self):
        # Simulate agent FAILING to block a massive trade
        self.mock_runner.side_effect = lambda action, payload: "Trade Executed" if payload['amount'] > 1000 else "BLOCKED"

        # Capture INFO and above to get both CRITICAL alert and INFO recommendation
        with self.assertLogs("AutoPT", level="INFO") as cm:
            self.loop.run_cycle()
            # We expect at least one critical alert for the massive amount attack
            self.assertTrue(any("Successful Attack Detected" in log for log in cm.output))
            self.assertTrue(any("BLUE TEAM RECOMMENDATION" in log for log in cm.output))

if __name__ == '__main__':
    unittest.main()
