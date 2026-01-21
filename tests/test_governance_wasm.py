import unittest
import json
import tempfile
import os
from unittest.mock import MagicMock, patch

# Import the code to be tested
from src.governance.engine import PolicyEngine
from src.governance.client import OPAClient, governed_tool

class TestWasmPolicyEngine(unittest.TestCase):

    def test_engine_initialization_no_file(self):
        """Test that engine handles missing policy file gracefully."""
        # Patching logger to avoid error noise in test output
        with patch('src.governance.engine.logger'):
            engine = PolicyEngine(policy_path="non_existent.wasm")
            self.assertFalse(engine.ready)
            # Should fail closed
            result = engine.evaluate({"action": "test"})
            self.assertEqual(result.get("result"), "DENY")

    def test_engine_mock_policy(self):
        """Test engine with a mocked Wasm policy."""
        # Create a dummy file so os.path.exists passes
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"fake_wasm_content")
            tmp_path = tmp.name

        try:
            # Mock the OPAPolicy class since we don't have a real Wasm here
            with patch('src.governance.engine.OPAPolicy') as MockPolicy:
                mock_instance = MockPolicy.return_value
                mock_instance.evaluate.return_value = {"result": "ALLOW"}

                engine = PolicyEngine(policy_path=tmp_path)

                self.assertTrue(engine.ready)

                # Test evaluation
                input_data = {"action": "trade", "amount": 100}
                result = engine.evaluate(input_data)

                # Check if evaluate was called with JSON string
                mock_instance.evaluate.assert_called_once_with(json.dumps(input_data))
                self.assertEqual(result["result"], "ALLOW")
        finally:
            os.remove(tmp_path)

class TestOPAClientWasm(unittest.TestCase):

    def setUp(self):
        # Reset the singleton if needed or mock it in the client module
        pass

    @patch('src.governance.client.PolicyEngine')
    def test_client_evaluate_allow(self, MockEngine):
        """Test the OPAClient using the mocked PolicyEngine."""
        # Setup mock engine behavior
        mock_engine_instance = MockEngine.return_value
        mock_engine_instance.evaluate.return_value = {"result": "ALLOW"}

        # Re-instantiate client to use the mock
        client = OPAClient()

        decision = client.evaluate_policy({"action": "test"})
        self.assertEqual(decision, "ALLOW")

    @patch('src.governance.client.PolicyEngine')
    def test_client_evaluate_deny(self, MockEngine):
        """Test the OPAClient using the mocked PolicyEngine."""
        mock_engine_instance = MockEngine.return_value
        mock_engine_instance.evaluate.return_value = {"result": "DENY"}

        client = OPAClient()
        decision = client.evaluate_policy({"action": "dangerous"})
        self.assertEqual(decision, "DENY")

    @patch('src.governance.client.PolicyEngine')
    def test_client_exception_handling(self, MockEngine):
        """Test that client fails closed (DENY) on engine exception."""
        mock_engine_instance = MockEngine.return_value
        mock_engine_instance.evaluate.side_effect = Exception("Wasm Crash")

        client = OPAClient()
        # Suppress logging for test
        with patch('src.governance.client.logger'):
            decision = client.evaluate_policy({"action": "test"})
            self.assertEqual(decision, "DENY")

if __name__ == '__main__':
    unittest.main()
