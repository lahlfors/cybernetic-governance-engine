import sys
import unittest
from unittest.mock import MagicMock, patch
import os

# --- PRE-IMPORT MOCKS ---
sys.modules["opentelemetry"] = MagicMock()
sys.modules["opentelemetry.trace"] = MagicMock()
sys.modules["google.adk.agents"] = MagicMock()
sys.modules["google.adk.tools"] = MagicMock()
sys.modules["financial_advisor.telemetry"] = MagicMock()
sys.modules["financial_advisor.nemo_manager"] = MagicMock()

# Mock langchain_google_genai
# We need to make sure the module has the class attribute for import
mock_langchain_module = MagicMock()
class MockChatGoogleGenerativeAI:
    def __init__(self, **kwargs):
        pass
    def invoke(self, prompt):
        return MagicMock()

mock_langchain_module.ChatGoogleGenerativeAI = MockChatGoogleGenerativeAI
sys.modules["langchain_google_genai"] = mock_langchain_module

# Mock google.auth
mock_google = MagicMock()
mock_auth = MagicMock()
mock_auth.default.return_value = (None, "test-project")
mock_auth.exceptions.DefaultCredentialsError = Exception
mock_google.auth = mock_auth
sys.modules["google"] = mock_google
sys.modules["google.auth"] = mock_auth

# Mock LlmAgent base class
class MockLlmAgent:
    def __init__(self, **kwargs):
        pass
    def __call__(self, prompt):
        return "Standard Agent Response"

sys.modules["google.adk.agents"].LlmAgent = MockLlmAgent

# Mock genai_span
class MockGenAiSpan:
    def __init__(self, name, **kwargs):
        pass
    def __enter__(self):
        return MagicMock()
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

sys.modules["financial_advisor.telemetry"].genai_span = MockGenAiSpan

# Mock sub-agents
sys.modules["financial_advisor.sub_agents.data_analyst"] = MagicMock()
sys.modules["financial_advisor.sub_agents.execution_analyst"] = MagicMock()
sys.modules["financial_advisor.sub_agents.governed_trader.agent"] = MagicMock()
sys.modules["financial_advisor.sub_agents.risk_analyst"] = MagicMock()
sys.modules["financial_advisor.tools.router"] = MagicMock()
sys.modules["financial_advisor.prompt"] = MagicMock()

os.environ["GOOGLE_CLOUD_PROJECT"] = "test-project"

# --- IMPORTS ---
# Import the modules under test
from financial_advisor import consensus
from financial_advisor.consensus import ConsensusEngine
from financial_advisor.agent import GovernedLlmAgent

class TestRefactoring(unittest.TestCase):

    def test_consensus_engine_approval(self):
        """Test that ConsensusEngine returns APPROVE when both critics approve."""
        engine = ConsensusEngine(threshold=100.0)

        # DEBUG: Check if the class is actually in the module
        # print("DEBUG: consensus attributes:", dir(consensus))

        # Instead of patching 'financial_advisor.consensus.ChatGoogleGenerativeAI',
        # let's patch the class in the source module, which is what consensus.py imported.
        # However, since we mocked sys.modules['langchain_google_genai'],
        # consensus.ChatGoogleGenerativeAI IS sys.modules['langchain_google_genai'].ChatGoogleGenerativeAI

        # So we can just inspect the mock directly!
        mock_llm_class = sys.modules["langchain_google_genai"].ChatGoogleGenerativeAI

        # But we need to reset it for the test
        # Create a new MagicMock to act as the instance
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "APPROVE - Looks good."
        mock_instance.invoke.return_value = mock_response

        # Configure the class mock to return our instance
        # The class mock is likely already instantiated in the code, so we need to mock the INSTANTIATION
        # We can do this by assigning side_effect to the class mock
        mock_llm_class.return_value = mock_instance

        # Reset call count from previous tests/imports
        mock_instance.invoke.reset_mock()
        mock_llm_class.reset_mock()

        # Act
        result = engine.check_consensus("BUY", 1000.0, "AAPL")

        # Assert
        self.assertEqual(result["status"], "APPROVE")
        # Should be called twice
        self.assertEqual(mock_instance.invoke.call_count, 2)
        print("\n✅ Consensus Engine: Correctly required 2 approvals.")

    def test_consensus_engine_rejection(self):
        """Test that ConsensusEngine returns REJECT if one critic objects."""
        engine = ConsensusEngine(threshold=100.0)

        mock_llm_class = sys.modules["langchain_google_genai"].ChatGoogleGenerativeAI
        mock_instance = MagicMock()
        mock_llm_class.return_value = mock_instance

        resp1 = MagicMock()
        resp1.content = "APPROVE - OK"
        resp2 = MagicMock()
        resp2.content = "REJECT - Too risky"
        mock_instance.invoke.side_effect = [resp1, resp2]

        # Act
        result = engine.check_consensus("BUY", 1000.0, "TSLA")

        # Assert
        self.assertEqual(result["status"], "REJECT")
        print("\n✅ Consensus Engine: Correctly rejected split vote.")

    def test_governed_agent_rails(self):
        """Test that GovernedLlmAgent uses NeMo rails when active."""

        mock_rails = MagicMock()
        mock_rails.generate.return_value = "Guarded Response"

        with patch("financial_advisor.agent.create_nemo_manager", return_value=mock_rails):
            agent = GovernedLlmAgent(name="test")
            # Ensure active
            agent._rails_active = True

            # Act
            response = agent("Hello")

            # Assert
            self.assertEqual(response, "Guarded Response")
            mock_rails.generate.assert_called_once()
            print("\n✅ Governed Agent: Correctly delegated to NeMo Guardrails.")

if __name__ == "__main__":
    unittest.main()
