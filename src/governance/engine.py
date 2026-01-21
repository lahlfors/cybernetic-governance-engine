import json
import logging
import os
import ctypes
from typing import Dict, Any, Optional

try:
    from wasmtime import Store, Module, Instance, Engine, Linker, WasiConfig
except ImportError:
    # Fail fast if wasmtime is missing
    raise ImportError("wasmtime library is required for PolicyEngine")

logger = logging.getLogger("GovernanceEngine")

class PolicyEngine:
    """
    Architecture II: Real Wasm Execution via Wasmtime.
    No mocks required. Runs natively in CI and Cloud Run.
    """
    def __init__(self, policy_path: str = "policy.wasm"):
        self.ready = False
        self.store = None
        self.instance = None

        if not os.path.exists(policy_path):
            msg = f"CRITICAL: Policy file not found at {policy_path}. Governance cannot be enforced."
            logger.critical(msg)
            raise FileNotFoundError(msg)

        try:
            # 1. Initialize Wasmtime Runtime
            engine = Engine()
            self.store = Store(engine)

            # 2. Load the Policy Module
            with open(policy_path, "rb") as f:
                module = Module(engine, f.read())

            linker = Linker(engine)

            # 3. Define WASI (System Interface) - OPA needs this for memory management
            wasi_config = WasiConfig()
            self.store.set_wasi(wasi_config)
            linker.define_wasi()

            # 4. Instantiate
            self.instance = linker.instantiate(self.store, module)

            # 5. Extract OPA Built-in Functions
            exports = self.instance.exports(self.store)

            # Helper to safely get export
            def get_export(name):
                return exports[name]

            self.opa_eval = get_export("opa_eval_ctx")
            self.opa_json_dump = get_export("opa_json_dump")
            self.opa_value_parse = get_export("opa_value_parse")
            self.opa_malloc = get_export("opa_malloc")
            self.memory = get_export("memory")

            # Initialize OPA Context (Heap)
            # opa_eval_ctx_new returns a pointer (i32)
            self.ctx = get_export("opa_eval_ctx_new")(self.store)

            # Cache entrypoints
            self.opa_eval_ctx_set_input = get_export("opa_eval_ctx_set_input")
            self.opa_eval_ctx_get_result = get_export("opa_eval_ctx_get_result")

            self.ready = True
            logger.info(f"✅ Wasmtime Engine Loaded: {policy_path}")

        except Exception as e:
            logger.critical(f"🔥 Wasm Engine Init Failed: {e}")
            raise e

    def _read_json_from_memory(self, addr: int) -> Dict[str, Any]:
        """
        Reads a null-terminated JSON string from Wasm memory at the given address.
        """
        # Access memory as a bytearray
        mem_data = self.memory.read(self.store, addr, self.memory.data_len(self.store) - addr)

        # Find null terminator
        try:
            null_idx = mem_data.index(0)
        except ValueError:
            # Fallback if no null terminator found (should not happen with OPA)
            null_idx = len(mem_data)

        json_bytes = mem_data[:null_idx]
        return json.loads(json_bytes.decode("utf-8"))

    def evaluate(self, input_data: Dict[str, Any], entrypoint: str = "finance/allow") -> Dict[str, Any]:
        """
        Executes the policy against the input data.
        """
        if not self.ready:
            return {"result": "DENY"}

        try:
            # 1. Serialize Input to JSON string
            input_json = json.dumps(input_data).encode("utf-8")

            # 2. Write Input to Wasm Memory
            # Allocate memory in Wasm
            input_ptr = self.opa_malloc(self.store, len(input_json))

            # Write bytes to memory
            # Wasmtime memory.write(store, value, offset)
            # Fix: Correct signature matches python help(Memory.write) -> write(store, value, offset)
            self.memory.write(self.store, input_json, input_ptr)

            # 3. Parse Input inside Wasm
            value_ptr = self.opa_value_parse(self.store, input_ptr, len(input_json))

            # 4. Set Input and Evaluate
            self.opa_eval_ctx_set_input(self.store, self.ctx, value_ptr)
            self.opa_eval(self.store, self.ctx)

            # 5. Get Result
            result_ptr = self.opa_eval_ctx_get_result(self.store, self.ctx)
            json_ptr = self.opa_json_dump(self.store, result_ptr)

            # 6. Read JSON from Wasm Memory
            result_doc = self._read_json_from_memory(json_ptr)

            return result_doc

        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            return {"result": "DENY"}
