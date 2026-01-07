import sys
import unittest
from unittest.mock import MagicMock, patch
import os

# ==========================================
# PHASE 1: PRE-IMPORT MOCKING
# ==========================================
# We must mock these massive dependencies to avoid ImportError
sys.modules["opentelemetry"] = MagicMock()
sys.modules["opentelemetry.trace"] = MagicMock()
sys.modules["google.adk.agents"] = MagicMock()
sys.modules["google.adk.tools"] = MagicMock()
sys.modules["financial_advisor.telemetry"] = MagicMock()
sys.modules["financial_advisor.nemo_manager"] = MagicMock()
sys.modules["langchain_google_genai"] = MagicMock()
sys.modules["nemoguardrails"] = MagicMock()

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

# ==========================================
# PHASE 2: IMPORTS
# ==========================================
try:
    from financial_advisor.consensus import ConsensusEngine
    from financial_advisor.agent import GovernedLlmAgent
    from financial_advisor import agent as agent_module
except ImportError as e:
    print(f"\nCRITICAL IMPORT ERROR: {e}")
    sys.exit(1)

# ==========================================
# PHASE 3: TESTS
# ==========================================
class TestRefactoring(unittest.TestCase):

    def test_consensus_approval(self):
        """Test that positive votes result in approval."""
        print("\nTesting Consensus: APPROVAL...")

        # Patch the class exactly where it is used in consensus.py
        # This bypasses all 'sys.modules' ambiguity
        with patch("financial_advisor.consensus.ChatGoogleGenerativeAI") as MockClass:
            mock_instance = MockClass.return_value
            mock_message = MagicMock()
            mock_message.content = "APPROVE - Looks good."
            mock_instance.invoke.return_value = mock_message

            engine = ConsensusEngine(threshold=100.0)
            result = engine.check_consensus("BUY", 1000.0, "AAPL")

            self.assertEqual(result["status"], "APPROVE")
            self.assertEqual(mock_instance.invoke.call_count, 2)
            print(" -> Passed: Consensus returned APPROVE.")

    def test_consensus_rejection(self):
        """Test that a negative vote triggers rejection."""
        print("\nTesting Consensus: REJECTION...")

        with patch("financial_advisor.consensus.ChatGoogleGenerativeAI") as MockClass:
            mock_instance = MockClass.return_value
            msg1 = MagicMock()
            msg1.content = "APPROVE - OK"
            msg2 = MagicMock()
            msg2.content = "REJECT - Too risky"
            mock_instance.invoke.side_effect = [msg1, msg2]

            engine = ConsensusEngine(threshold=100.0)
            result = engine.check_consensus("BUY", 1000.0, "TSLA")

            self.assertEqual(result["status"], "REJECT")
            print(" -> Passed: Consensus returned REJECT.")

    @patch("financial_advisor.agent.create_nemo_manager")
    def test_governed_agent_success(self, mock_create_manager):
        """Verify Agent correctly routes safe input through Guardrails."""
        print("\nTesting Governed Agent: GUARDRAILS ACTIVE...")

        mock_rails = MagicMock()
        mock_create_manager.return_value = mock_rails

        # Important: generate() must return a dict
        mock_rails.generate.return_value = {
            "role": "assistant",
            "content": "Guarded Response"
        }

        # We also need to ensure LlmAgent.__init__ doesn't fail if we are mocking it
        # But GovernedLlmAgent inherits from the class we mocked in sys.modules
        # So it should be fine.

        agent = GovernedLlmAgent(name="TestAgent")

        # Force active state just in case
        agent._rails_active = True

        # Act
        # We need to capture stdout to see the error if it fails
        from io import StringIO
        captured_output = StringIO()
        sys.stdout = captured_output
        try:
            response = agent("Hello")
        finally:
            sys.stdout = sys.__stdout__ # Restore

        # Check output if fallback happened
        output = captured_output.getvalue()
        if "Error in NeMo Guardrails" in output:
             print(f"DEBUG: Captured Error: {output}")

        # Assertions
        if response == "Standard Agent Response":
            self.fail(f"Agent fell back to standard execution. Output: {output}")

        self.assertEqual(response, "Guarded Response")
        mock_rails.generate.assert_called_once()
        print(" -> Passed: Agent returned Guarded Response.")

if __name__ == "__main__":
    unittest.main()
