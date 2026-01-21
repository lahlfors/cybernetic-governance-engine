import unittest
import json
import tempfile
import os
import sys
from unittest.mock import MagicMock, patch

# Mock Strategy:
# We must ensure that the arguments passed to memory.write are correct according to wasmtime API.
# wasmtime.Memory.write(store, value, start)

# 1. Mock PolicyEngine for Client import
sys.modules['src.governance.engine'] = MagicMock()
mock_engine_class = MagicMock()
mock_engine_class.return_value.evaluate.return_value = {"result": "ALLOW"}
sys.modules['src.governance.engine'].PolicyEngine = mock_engine_class

from src.governance.client import OPAClient

# 2. Un-mock for real Engine testing
del sys.modules['src.governance.engine']
from src.governance.engine import PolicyEngine

class TestWasmPolicyEngine(unittest.TestCase):

    def test_engine_initialization_no_file(self):
        """Test that engine raises FileNotFoundError if policy file is missing."""
        with patch('src.governance.engine.logger'):
            # It should raise FileNotFoundError, which we might catch or not depending on impl.
            # Current impl raises it.
            with self.assertRaises(FileNotFoundError):
                PolicyEngine(policy_path="non_existent.wasm")

    @patch('src.governance.engine.Module')
    @patch('src.governance.engine.Linker')
    @patch('src.governance.engine.Store')
    @patch('src.governance.engine.Engine')
    def test_engine_evaluation_logic(self, MockEngine, MockStore, MockLinker, MockModule):
        """
        Test the PolicyEngine logic using mocked Wasmtime components.
        STRICT verification of API calls to ensure correctness.
        """
        # Create a dummy file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"\x00asm...")
            tmp_path = tmp.name

        try:
            # --- 1. Setup Singleton Mocks (Crucial for Reference Equality) ---
            mock_store_inst = MockStore.return_value
            mock_instance = MockLinker.return_value.instantiate.return_value

            # Define fake pointers
            INPUT_PTR = 100
            VALUE_PTR = 200
            CTX_PTR = 300
            RESULT_PTR = 400
            JSON_PTR = 500

            # Create specific function mocks
            mock_opa_malloc = MagicMock(return_value=INPUT_PTR)
            mock_opa_value_parse = MagicMock(return_value=VALUE_PTR)
            mock_opa_eval_ctx_new = MagicMock(return_value=CTX_PTR)
            mock_opa_eval_ctx_get_result = MagicMock(return_value=RESULT_PTR)
            mock_opa_json_dump = MagicMock(return_value=JSON_PTR)

            # Create the MEMORY mock (Singleton)
            mock_memory = MagicMock()
            mock_memory.read.return_value = b'{"result": "ALLOW"}\x00'
            mock_memory.data_len.return_value = 1024

            # --- 2. Configure the "Exports" Side Effect ---
            mock_exports = MagicMock()
            mock_instance.exports.return_value = mock_exports

            def get_export_side_effect(name):
                if name == "memory":
                    return mock_memory
                elif name == "opa_malloc":
                    return mock_opa_malloc
                elif name == "opa_value_parse":
                    return mock_opa_value_parse
                elif name == "opa_eval_ctx_new":
                    return mock_opa_eval_ctx_new
                elif name == "opa_eval_ctx_get_result":
                    return mock_opa_eval_ctx_get_result
                elif name == "opa_json_dump":
                    return mock_opa_json_dump
                return MagicMock() # Fallback

            mock_exports.__getitem__.side_effect = get_export_side_effect

            # Instantiate Engine
            engine = PolicyEngine(policy_path=tmp_path)
            self.assertTrue(engine.ready)

            # Execute Evaluation
            input_data = {"unsafe": True}
            result = engine.evaluate(input_data)

            # Assertions
            self.assertEqual(result["result"], "ALLOW")

            # STRICT VERIFICATION: Check memory.write arguments
            # Expected: write(store, input_json_bytes, input_ptr)

            # Ensure write was called on the SINGLETON mock
            self.assertTrue(mock_memory.write.called, "Memory.write was not called")

            args, _ = mock_memory.write.call_args

            # Arg 0: Store
            self.assertEqual(args[0], mock_store_inst)

            # Arg 1: Value (Bytes) - This is where the bug was!
            self.assertIsInstance(args[1], bytes, f"Arg 1 should be bytes (Data), got {type(args[1])}")
            self.assertEqual(args[1], json.dumps(input_data).encode("utf-8"))

            # Arg 2: Start (Int) - Offset
            self.assertIsInstance(args[2], int, f"Arg 2 should be int (Offset), got {type(args[2])}")
            self.assertEqual(args[2], INPUT_PTR)

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

if __name__ == '__main__':
    unittest.main()
