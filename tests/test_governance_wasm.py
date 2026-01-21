import unittest
import json
import tempfile
import os
import sys
from unittest.mock import MagicMock, patch

# 1. Mock the C-extension dependency before it's imported by application code
sys.modules['opa_wasm'] = MagicMock()
sys.modules['opa_wasm'].OPAPolicy = MagicMock()

# 2. Mock PolicyEngine BEFORE importing client, so module-level instantiation doesn't crash
# We create a dummy PolicyEngine that doesn't raise FileNotFoundError
mock_engine_cls = MagicMock()
mock_engine_cls.return_value.evaluate.return_value = {"result": "ALLOW"}
sys.modules['src.governance.engine'] = MagicMock()
sys.modules['src.governance.engine'].PolicyEngine = mock_engine_cls

# Now we can safely import the client
from src.governance.client import OPAClient

# But for testing PolicyEngine itself, we need the real class, so we reload or unpatch
# This is getting messy. Better approach:
# Let's import the *real* PolicyEngine for the Engine tests,
# and use the *mocked* one for the Client tests.

# Re-import real PolicyEngine for testing
del sys.modules['src.governance.engine']
from src.governance.engine import PolicyEngine

class TestWasmPolicyEngine(unittest.TestCase):

    def test_engine_initialization_no_file(self):
        """Test that engine raises FileNotFoundError if policy file is missing."""
        # Patching logger to avoid error noise
        with patch('src.governance.engine.logger'):
            with self.assertRaises(FileNotFoundError):
                PolicyEngine(policy_path="non_existent.wasm")

    def test_engine_mock_policy(self):
        """Test engine with a mocked Wasm policy."""
        # Create a dummy file so os.path.exists passes
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"fake_wasm_content")
            tmp_path = tmp.name

        try:
            # Setup the mocked OPA library
            mock_policy_class = sys.modules['opa_wasm'].OPAPolicy
            mock_instance = mock_policy_class.return_value
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
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

class TestOPAClientWasm(unittest.TestCase):

    def setUp(self):
        # We need to patch the singleton `opa_client` in the module
        pass

    def test_client_evaluate(self):
        """Test the OPAClient logic."""
        # Since OPAClient was instantiated at import time (likely failing or using mocks),
        # we construct a new one here with a patched engine for testing.

        with patch('src.governance.client.PolicyEngine') as MockEngine:
            mock_instance = MockEngine.return_value
            mock_instance.evaluate.return_value = {"result": "ALLOW"}

            client = OPAClient()
            decision = client.evaluate_policy({"action": "test"})
            self.assertEqual(decision, "ALLOW")

if __name__ == '__main__':
    unittest.main()
