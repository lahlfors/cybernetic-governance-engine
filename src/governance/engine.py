import json
import logging
import os
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger("GovernanceEngine")

class PolicyEngine:
    """
    Architecture 1.5: OPA Sidecar Client.
    Decoupled governance logic via Open Policy Agent.
    """
    def __init__(self, policy_url: str = None):
        self.opa_url = os.getenv("POLICY_URL", "http://localhost:8181/v1/data/banking/governance")
        logger.info(f"🛡️ OPA Client Initialized. Target: {self.opa_url}")

    def evaluate(self, input_data: Dict[str, Any], entrypoint: str = None) -> Dict[str, Any]:
        """
        Executes the policy by querying the OPA Sidecar.
        """
        try:
            # Map input to OPA format
            # Input data usually structure: {"action": "...", "context": {...}}
            # We flatten it for the Rego policy: {"input": {"action": ..., "amount": ..., "risk_score": ...}}

            action = input_data.get("action", "unknown_action")
            context = input_data.get("context", input_data)

            payload = {
                "input": {
                    "action": action,
                    # Spread context keys into input for easier Rego access
                    **context
                }
            }

            # Ultra-low latency localhost call
            response = requests.post(self.opa_url, json=payload, timeout=0.5)

            if response.status_code == 200:
                result = response.json()
                # OPA returns {"result": {"allow": true, ...}} or just {"result": true} depending on rule
                # Our policy defines `allow` as a boolean.
                # So result.json() -> {"result": {"allow": true}} ??
                # If we query the package `data.banking.governance`, result is `{"result": {"allow": true}}`

                allow = result.get("result", {}).get("allow", False)

                if allow:
                    return {"result": "ALLOW"}
                else:
                    return {"result": "DENY", "reason": "Policy Violation (OPA)"}
            else:
                logger.error(f"OPA returned {response.status_code}: {response.text}")
                return {"result": "DENY", "reason": "OPA Error"}

        except Exception as e:
            logger.error(f"OPA Evaluation failed: {e}")
            # Fail closed
            return {"result": "DENY", "reason": "Communication Failure"}
