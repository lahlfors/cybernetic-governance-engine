import functools
import logging
import os
import requests
from typing import Any, Dict
from pydantic import BaseModel
from opentelemetry import trace

# Configure logging
logger = logging.getLogger("GovernanceLayer")
tracer = trace.get_tracer("financial_advisor.governance")

class OPAClient:
    """
    Production-ready OPA Client.
    Fetches OPA_URL from environment to support seamless transition
    from Docker Compose -> Cloud Run.
    """
    def __init__(self):
        # Default to localhost for standalone testing, but allow override for Docker/Cloud
        self.url = os.environ.get("OPA_URL", "http://localhost:8181/v1/data/finance/allow")
        # Fetch authentication token if available
        self.auth_token = os.environ.get("OPA_AUTH_TOKEN")

    def check_policy(self, input_data: Dict[str, Any]) -> bool:
        with tracer.start_as_current_span("governance.check") as span:
            span.set_attribute("governance.opa_url", self.url)
            span.set_attribute("governance.action", input_data.get("action", "unknown"))

            headers = {}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"

            try:
                # We add a timeout to ensure governance doesn't hang the agent
                response = requests.post(
                    self.url,
                    json={"input": input_data},
                    headers=headers,
                    timeout=1.0
                )
                response.raise_for_status()

                result = response.json().get("result", False)
                span.set_attribute("governance.decision", "ALLOW" if result else "DENY")

                if result:
                    logger.info(f"✅ OPA ALLOWED | Action: {input_data.get('action')}")
                else:
                    logger.warning(f"⛔ OPA DENIED | Action: {input_data.get('action')} | Input: {input_data}")

                return result
            except Exception as e:
                # FAIL CLOSED: If security is down, nothing happens.
                logger.critical(f"🔥 OPA FAILURE: Could not connect to policy engine at {self.url}. Error: {e}")
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR))
                return False

# Instantiate the real client
opa_client = OPAClient()

def governed_tool(action_name: str):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 1. Layer 1: Pydantic Validation (Implicit)
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
                return "SYSTEM ERROR: Tool called without structured data schema."

            # 2. Layer 2: Policy Check
            payload = model_instance.model_dump()
            payload['action'] = action_name

            if not opa_client.check_policy(payload):
                return f"BLOCKED: Governance Policy Violation. {model_instance.model_dump()}"

            # 3. Execution
            return func(*args, **kwargs)
        return wrapper
    return decorator
