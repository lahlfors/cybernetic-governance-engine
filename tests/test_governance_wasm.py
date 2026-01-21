import unittest
import json
import tempfile
import os
import sys
from unittest.mock import MagicMock, patch

# Mock Strategy:
# We mock 'wasmtime' and ensure that 'memory.data_ptr(store)' returns a ctypes pointer.
# We verify that _write_to_memory calls ctypes.memmove with correct arguments.

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
            with self.assertRaises(FileNotFoundError):
                PolicyEngine(policy_path="non_existent.wasm")

    @patch('src.governance.engine.Module')
    @patch('src.governance.engine.Linker')
    @patch('src.governance.engine.Store')
    @patch('src.governance.engine.Engine')
    @patch('src.governance.engine.ctypes') # Mock ctypes to verify memmove/string_at
    def test_engine_evaluation_logic(self, MockCtypes, MockEngine, MockStore, MockLinker, MockModule):
        """
        Test the PolicyEngine logic using mocked Wasmtime components and ctypes.
        STRICT verification of memory operations.
        """
        # Create a dummy file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"\x00asm...")
            tmp_path = tmp.name

        try:
            # --- Setup Mocks ---
            mock_store_inst = MockStore.return_value
            mock_instance = MockLinker.return_value.instantiate.return_value

            # Pointers
            INPUT_PTR = 100
            VALUE_PTR = 200
            CTX_PTR = 300
            RESULT_PTR = 400
            JSON_PTR = 500
            BASE_ADDR = 1000 # Fake base address of Wasm memory
            MEMORY_SIZE = 10000

            # Mock functions
            mock_opa_malloc = MagicMock(return_value=INPUT_PTR)
            mock_opa_value_parse = MagicMock(return_value=VALUE_PTR)
            mock_opa_eval_ctx_new = MagicMock(return_value=CTX_PTR)
            mock_opa_eval_ctx_get_result = MagicMock(return_value=RESULT_PTR)
            mock_opa_json_dump = MagicMock(return_value=JSON_PTR)

            # Memory Mock
            mock_memory = MagicMock()
            # data_ptr should return a pointer.
            mock_data_ptr = MagicMock()
            mock_memory.data_ptr.return_value = mock_data_ptr
            # data_len should return int
            mock_memory.data_len.return_value = MEMORY_SIZE

            # Setup ctypes mock behavior
            # cast(ptr, void_p).value should return BASE_ADDR
            mock_void_p_obj = MagicMock()
            mock_void_p_obj.value = BASE_ADDR
            MockCtypes.cast.return_value = mock_void_p_obj

            # string_at(addr) -> return bytes
            MockCtypes.string_at.return_value = b'{"result": "DENY"}' # Simulate DENY result

            # Exports side effect
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
                return MagicMock()

            mock_exports.__getitem__.side_effect = get_export_side_effect

            # Instantiate Engine
            engine = PolicyEngine(policy_path=tmp_path)
            self.assertTrue(engine.ready)

            # Execute Evaluation
            # We use input {"unsafe": True} and expect DENY (as returned by string_at mock)
            input_data = {"unsafe": True}
            result = engine.evaluate(input_data)

            # Assertions
            self.assertEqual(result["result"], "DENY")

            # STRICT VERIFICATION: Check memmove arguments (Write)
            # Code: ctypes.memmove(target_addr, data, len(data))
            # target_addr = BASE_ADDR + INPUT_PTR = 1000 + 100 = 1100

            MockCtypes.memmove.assert_called()
            args, _ = MockCtypes.memmove.call_args

            # Arg 0: Destination Address
            self.assertEqual(args[0], BASE_ADDR + INPUT_PTR)

            # Arg 1: Source Data (Bytes)
            expected_json = json.dumps(input_data).encode("utf-8")
            self.assertEqual(args[1], expected_json)

            # Arg 2: Length
            self.assertEqual(args[2], len(expected_json))

            # STRICT VERIFICATION: Check string_at arguments (Read)
            # Code: ctypes.string_at(target_addr)
            # target_addr = BASE_ADDR + JSON_PTR = 1000 + 500 = 1500

            MockCtypes.string_at.assert_called()
            r_args, _ = MockCtypes.string_at.call_args
            self.assertEqual(r_args[0], BASE_ADDR + JSON_PTR)

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

if __name__ == '__main__':
    unittest.main()
