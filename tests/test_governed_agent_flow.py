import unittest
from google.adk.agents import SequentialAgent, LlmAgent
from financial_advisor.sub_agents.governed_trader.agent import governed_trading_agent

class TestGovernedAgentFlow(unittest.TestCase):

    def test_agent_structure(self):
        """Test that the governed agent is correctly wired as a SequentialAgent."""
        print("\n[Structure] Verifying Governed Trading Agent...")

        # Check type
        self.assertIsInstance(governed_trading_agent, SequentialAgent)
        print(" - Validated Agent Type: SequentialAgent")

        # Check sub-agents length
        self.assertEqual(len(governed_trading_agent.sub_agents), 2)
        print(f" - Validated Sub-agents Count: {len(governed_trading_agent.sub_agents)}")

        # Check sub-agent names
        worker = governed_trading_agent.sub_agents[0]
        verifier = governed_trading_agent.sub_agents[1]

        self.assertEqual(worker.name, "worker_agent")
        print(" - Validated Step 1: worker_agent")

        self.assertEqual(verifier.name, "verifier_agent")
        print(" - Validated Step 2: verifier_agent")

        # Check tools on worker
        self.assertTrue(hasattr(worker, 'tools'))
        self.assertTrue(len(worker.tools) > 0)
        print(" - Validated Worker has tools attached (FunctionTool)")

if __name__ == '__main__':
    unittest.main()
