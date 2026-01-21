import json
import logging
import os
from typing import Dict, Any, Optional

# Try to import opa_wasm, but handle the case where it might be missing in some environments
# (though we installed it, this is good practice for portability)
try:
    from opa_wasm import OPAPolicy
except ImportError:
    OPAPolicy = None

logger = logging.getLogger("GovernanceEngine")

class PolicyEngine:
    """
    In-Process Policy Engine using OPA WebAssembly (Wasm).
    Replaces the HTTP Sidecar for <1ms decision latency.
    """

    def __init__(self, policy_path: str = "policy.wasm"):
        """
        Initialize the policy engine by loading the compiled Wasm file.

        Args:
            policy_path: Path to the compiled 'policy.wasm' file.
        """
        self.policy: Optional[OPAPolicy] = None
        self.ready = False

        if not OPAPolicy:
            logger.error("opa_wasm library not found. Policy checks will fail open or closed based on configuration.")
            return

        if not os.path.exists(policy_path):
            logger.warning(f"⚠️ Policy file not found at {policy_path}. Governance is NOT active.")
            return

        try:
            with open(policy_path, "rb") as f:
                policy_data = f.read()
                self.policy = OPAPolicy(policy_data)
                self.ready = True
            logger.info(f"✅ Loaded OPA Policy from {policy_path}")
        except Exception as e:
            logger.critical(f"🔥 Failed to load OPA Policy: {e}")

    def evaluate(self, input_data: Dict[str, Any], entrypoint: str = "finance/allow") -> Dict[str, Any]:
        """
        Executes the policy against the input data.

        Args:
            input_data: The JSON-serializable input dictionary (e.g., {"action": "trade", ...}).
            entrypoint: The entrypoint in the Wasm policy (not used directly by opa-wasm
                        if the wasm was built with a specific entrypoint, but useful for context).
                        Note: opa-wasm 'evaluate' takes the full input and returns the full result
                        set defined at build time.

        Returns:
            The policy evaluation result (typically a dict like {"result": "ALLOW"}).
        """
        if not self.ready or not self.policy:
            # FAIL SAFE: If policy system is down, we must decide to Fail Open or Closed.
            # For High Risk Finance: FAIL CLOSED (DENY).
            logger.error("PolicyEngine not ready. Defaulting to DENY.")
            return {"result": "DENY"}

        try:
            # opa-wasm requires the input to be a JSON string
            input_json = json.dumps(input_data)

            # evaluate() returns the full document defined by the entrypoint at build time
            result = self.policy.evaluate(input_json)

            return result
        except Exception as e:
            logger.error(f"Error during policy evaluation: {e}")
            return {"result": "DENY"}
