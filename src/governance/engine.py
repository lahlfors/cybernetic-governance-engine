import json
import logging
import os
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger("GovernanceEngine")

class PolicyEngine:
    """
    Architecture III: Cloud Run Sidecar Guard.
    Replaces In-Process Wasm with HTTP Sidecar calls.
    """
    def __init__(self, policy_path: str = None):
        # Policy path is ignored in this architecture, but kept for compatibility
        self.guard_url = os.getenv("GUARD_URL", "http://localhost:9000")
        logger.info(f"🛡️ Sidecar Policy Engine Initialized. Target: {self.guard_url}")

    def evaluate(self, input_data: Dict[str, Any], entrypoint: str = "finance/allow") -> Dict[str, Any]:
        """
        Executes the policy by calling the Sidecar Guard.
        """
        try:
            # Map OPA-style input to Sidecar ActionRequest
            # Input data usually structure: {"input": { ... }} or just raw dict depending on caller.
            # We assume input_data contains 'action' and 'context' or we infer it.

            # Basic mapping logic:
            # If the caller sends a raw dict, we assume it *is* the context,
            # and we need an action name.

            action = input_data.get("action", "unknown_action")
            context = input_data.get("context", input_data)

            payload = {
                "action": action,
                "context": context
            }

            response = requests.post(f"{self.guard_url}/execute_action", json=payload, timeout=2.0)

            if response.status_code == 200:
                result = response.json()
                if result.get("allowed"):
                    return {"result": "ALLOW"}
                else:
                    return {"result": "DENY", "reason": result.get("reason")}
            else:
                logger.error(f"Sidecar returned {response.status_code}: {response.text}")
                return {"result": "DENY", "reason": "Sidecar Error"}

        except Exception as e:
            logger.error(f"Sidecar Evaluation failed: {e}")
            return {"result": "DENY", "reason": "Communication Failure"}
