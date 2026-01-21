import functools
import logging
import os
from typing import Any, Dict, Union
from pydantic import BaseModel
from opentelemetry import trace
from src.utils.telemetry import genai_span
from src.governance.consensus import consensus_engine
from src.governance.safety import safety_filter
from src.governance.engine import PolicyEngine
from config.settings import Config

# Configure logging
logger = logging.getLogger("GovernanceLayer")
tracer = trace.get_tracer("src.governance.client")

class OPAClient:
    """
    Architecture II: In-Process OPA Client.
    Uses opa-wasm for <1ms policy checks.
    """
    def __init__(self):
        # Initialize the Policy Engine with the configured Wasm path
        # Uses Config.OPA_WASM_PATH which ensures centralized configuration
        self.engine = PolicyEngine(policy_path=Config.OPA_WASM_PATH)

    def evaluate_policy(self, input_data: Dict[str, Any]) -> str:
        """
        Evaluates the policy and returns the decision: ALLOW, DENY, or MANUAL_REVIEW.
        """
        with tracer.start_as_current_span("governance.check") as span:
            span.set_attribute("governance.type", "wasm_in_process")
            span.set_attribute("governance.action", input_data.get("action", "unknown"))

            try:
                # Execute In-Process Wasm Check
                result_data = self.engine.evaluate(input_data)

                # Extract the result string (defaulting to DENY)
                # Note: The structure of result_data depends on the query used during 'opa build'.
                # Assuming 'result' field in the output document.
                result = result_data.get("result", "DENY")

                span.set_attribute("governance.decision", result)

                if result == "ALLOW":
                    logger.info(f"✅ OPA ALLOWED | Action: {input_data.get('action')}")
                elif result == "MANUAL_REVIEW":
                     logger.warning(f"⚠️ OPA MANUAL REVIEW | Action: {input_data.get('action')}")
                else:
                    logger.warning(f"⛔ OPA DENIED | Action: {input_data.get('action')} | Input: {input_data}")

                return result
            except Exception as e:
                # FAIL CLOSED
                logger.critical(f"🔥 OPA FAILURE: Engine Evaluation Error: {e}")
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR))
                return "DENY"

    # Backward compatibility wrapper
    def check_policy(self, input_data: Dict[str, Any]) -> bool:
         decision = self.evaluate_policy(input_data)
         return decision == "ALLOW"

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

            payload = model_instance.model_dump()
            payload['action'] = action_name

            # 2. Layer 2: Policy Check (OPA)
            decision = opa_client.evaluate_policy(payload)

            if decision == "DENY":
                return f"BLOCKED: Governance Policy Violation. {payload}"

            if decision == "MANUAL_REVIEW":
                return "PENDING_HUMAN_REVIEW: Policy triggered Manual Intervention."

            # 3. Layer 3.5: Mathematical Safety (CBF) - Integrated before Consensus
            cbf_result = safety_filter.verify_action(action_name, payload)
            if cbf_result.startswith("UNSAFE"):
                 return f"BLOCKED: Mathematical Safety Violation (CBF). {cbf_result}"

            # 4. Layer 4: Consensus Check (High Stakes)
            # Only for execution, not proposal (which is cheap)
            if action_name == "execute_trade":
                amount = payload.get("amount", 0)
                symbol = payload.get("symbol", "UNKNOWN")
                consensus = consensus_engine.check_consensus(action_name, amount, symbol)
                if consensus["status"] == "REJECT":
                     return f"BLOCKED: Consensus Engine Rejected. {consensus['reason']}"

                if consensus["status"] == "ESCALATE":
                     return f"MANUAL_REVIEW: Consensus Engine Escalation. {consensus['reason']}"

                # If we pass all checks, update the safety state (Simulation)
                safety_filter.update_state(amount)

            # 5. Execution (ALLOW)
            with genai_span(f"tool.execution.{action_name}"):
                 return func(*args, **kwargs)

        return wrapper
    return decorator
