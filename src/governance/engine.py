import json
import logging
import os
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger("GovernanceEngine")

class PolicyEngine:
    """
    Architecture 1.5: OPA Sidecar Client with Tri-State Protocol.
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

                # Check for Tri-State 'analysis' object
                # Structure: {"result": {"analysis": {"status": "ALLOW/DENY/UNCERTAIN", "reason": "..."}}}
                analysis = result.get("result", {}).get("analysis", {})

                status = analysis.get("status")
                reason = analysis.get("reason", "No reason provided")

                if status:
                    return {"status": status, "reason": reason}

                # Fallback for boolean policies (backward compatibility)
                allow = result.get("result", {}).get("allow", False)
                if allow:
                    return {"status": "ALLOW", "reason": "Explicit Allow"}
                else:
                    return {"status": "DENY", "reason": "Policy Violation (Implicit)"}

            else:
                logger.error(f"OPA returned {response.status_code}: {response.text}")
                return {"status": "UNCERTAIN", "reason": "OPA Error"}

        except Exception as e:
            logger.error(f"OPA Evaluation failed: {e}")
            return {"status": "DENY", "reason": "Communication Failure"}
