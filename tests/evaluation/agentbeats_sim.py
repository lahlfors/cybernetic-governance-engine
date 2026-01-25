import unittest

from src.evaluator_agent.simulator import AgentBeatsSimulator, mock_financial_agent


class TestAgentBeats(unittest.TestCase):
    def test_simulation_run(self):
        """Test that the simulator runs a loop and produces a graded report."""
        sim = AgentBeatsSimulator(mock_financial_agent)

        # Run 2 scenarios
        report = sim.run_simulation(num_scenarios=2, use_red_team=True)

        self.assertEqual(report["total_runs"], 2)
        self.assertIn("pass_rate", report)
        self.assertTrue(0.0 <= report["pass_rate"] <= 1.0)

        # Check details
        for result in report["details"]:
            self.assertIn("score", result)
            self.assertIn("explanation", result)
            # Ensure the Red Agent injected something
            self.assertTrue(len(result["prompt"]) > 0)

if __name__ == "__main__":
    unittest.main()
