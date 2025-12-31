import functools
import logging
import os
import requests
from pydantic import BaseModel

# Configure logging
logger = logging.getLogger("GovernanceSystem")

class OPAClient:
    """
    Connects to a real running OPA server.
    """
    def __init__(self, url: str = None):
        self.url = url or os.environ.get("OPA_URL", "http://localhost:8181/v1/data/finance/allow")

    def check_policy(self, input_data: dict) -> bool:
        """
        Sends the input data to the OPA Engine for a decision.
        """
        try:
            # OPA expects the payload to be wrapped in "input"
            payload = {"input": input_data}

            # The actual HTTP call to the policy engine
            response = requests.post(self.url, json=payload)
            response.raise_for_status()

            # OPA returns JSON like: {"result": true} or {"result": false}
            result = response.json().get("result", False)

            logger.info(f"[OPA Server] Checked Policy. Decision: {'ALLOW' if result else 'DENY'}")
            return result

        except requests.exceptions.RequestException as e:
            logger.critical(f"[OPA Server] Connection Failed: {e}")
            return False

# Instantiate the real client
opa_client = OPAClient()

def governed_tool(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Helper to find the Pydantic model
        model_instance = None
        for arg in args:
            if isinstance(arg, BaseModel):
                model_instance = arg
                break
        if not model_instance:
            for _, value in kwargs.items():
                if isinstance(value, BaseModel):
                    model_instance = value
                    break

        if not model_instance:
            raise ValueError("Tool must be called with a Pydantic model.")

        # --- Layer 2 Check ---
        logger.info(f"[Governance] Requesting approval for: {model_instance}")
        is_allowed = opa_client.check_policy(model_instance.model_dump())

        if not is_allowed:
            return f"BLOCKED: OPA Policy Violation. Transaction details: {model_instance.model_dump()}"

        return func(*args, **kwargs)

    return wrapper
