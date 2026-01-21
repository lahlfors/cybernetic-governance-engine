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
        Uses ctypes for raw memory access to ensure compatibility.
        """
        # Get raw pointer to the start of Wasm memory
        base_ptr = self.memory.data_ptr(self.store)

        # Calculate the absolute address in host memory
        # We need to cast the base_ptr (c_ubyte pointer) to a void pointer or address
        # ctypes pointers support arithmetic.

        # Safe reading loop to find null terminator
        # We read chunk by chunk or byte by byte. Since JSON is contiguous, we can scan.
        # But scanning safely in python is slow. OPA JSON is usually small.

        # Direct access using ctypes string_at (reads until null terminator)
        # Note: data_ptr returns a POINTER(c_ubyte).
        # We need to access base_ptr[addr].

        # Validate bounds
        data_len = self.memory.data_len(self.store)
        if addr >= data_len:
             raise ValueError("Memory access out of bounds")

        # Create a pointer to the string start
        # base_ptr is the start of memory. string is at base_ptr + addr.
        # Python ctypes pointer arithmetic: ptr + offset

        # We must be careful: data_ptr is valid only as long as store/memory isn't grown.
        # In this short execution scope, it's fine.

        # cast to char pointer for string_at
        char_ptr = ctypes.cast(base_ptr, ctypes.POINTER(ctypes.c_char))

        # Read null-terminated string from offset
        # string_at(ptr, size=-1) reads until null if size not given?
        # Actually string_at(ptr) reads until null.
        # We need the address: ctypes.addressof(base_ptr.contents) + addr?
        # data_ptr returns a pointer object.

        # Correct way with wasmtime's pointer:
        # raw_ptr_val = ctypes.addressof(base_ptr.contents) # This might fail if it's a special object
        # but wasmtime docs say it returns ctypes.POINTER(ctypes.c_ubyte).

        # Let's use the buffer protocol if available or simple pointer arithmetic.
        # string_at expects an address (int) or a pointer instance.

        # Pointer arithmetic in ctypes:
        # If base_ptr is POINTER(c_ubyte), then base_ptr[addr] gives the value.
        # We want a pointer TO that index.

        # Solution: Use ctypes.byref logic or cast.
        # Better: string_at(ctypes.cast(base_ptr, ctypes.c_void_p).value + addr)

        raw_base_addr = ctypes.cast(base_ptr, ctypes.c_void_p).value
        if raw_base_addr is None:
             raise ValueError("Null memory pointer")

        target_addr = raw_base_addr + addr

        # Read string
        json_bytes = ctypes.string_at(target_addr)

        return json.loads(json_bytes.decode("utf-8"))

    def _write_to_memory(self, data: bytes, addr: int):
        """
        Writes bytes to Wasm memory at the given address.
        """
        base_ptr = self.memory.data_ptr(self.store)
        raw_base_addr = ctypes.cast(base_ptr, ctypes.c_void_p).value

        target_addr = raw_base_addr + addr

        # Use memmove to copy bytes
        ctypes.memmove(target_addr, data, len(data))

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

            # Write bytes to memory using ctypes
            self._write_to_memory(input_json, input_ptr)

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
