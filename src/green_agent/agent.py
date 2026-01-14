import logging
from typing import Dict, Any, Literal
from pydantic import BaseModel

from src.governance.client import OPAClient

# Configure logging
logger = logging.getLogger("GreenAgent")

class GreenAgentResult(BaseModel):
    status: Literal["APPROVED", "REJECTED"]
    feedback: str

class GreenAgent:
    """
    The 'Green Agent' acts as a Verified Evaluator (System 2 Verification).
    It audits plans against the Constitution (OPA Policy) and System Safety checks.
    """
    def __init__(self):
        self.opa_client = OPAClient()

    def audit_plan(self, plan_text: str) -> GreenAgentResult:
        """
        Audits a proposed plan (textual strategy) against governance rules.
        """
        logger.info("--- [Green Agent] Auditing Plan ---")

        # 1. Structural/Policy Check via OPA
        # We treat the plan verification as a "verify_plan" action.
        # In a real scenario, we would parse the plan_text into structured data.
        # For now, we pass the raw text to OPA to check for prohibited keywords/intents.
        policy_payload = {
            "action": "verify_plan",
            "resource": {
                "type": "trading_strategy",
                "content": plan_text
            }
        }

        policy_decision = self.opa_client.evaluate_policy(policy_payload)

        if policy_decision == "DENY":
            logger.warning("--- [Green Agent] Plan REJECTED by Policy ---")
            return GreenAgentResult(
                status="REJECTED",
                feedback="Governance Policy Violation: The plan contains prohibited elements or strategies."
            )

        if policy_decision == "MANUAL_REVIEW":
             logger.warning("--- [Green Agent] Plan Escalated for Manual Review ---")
             return GreenAgentResult(
                status="REJECTED",
                feedback="Policy requires Human Review. Plan cannot be auto-approved."
            )

        # 2. Mock System Safety Check (STPA - Unsafe Control Actions)
        # Placeholder for Module 4.1 logic.
        # Simple heuristic: Check for obviously unsafe instructions if not caught by OPA.
        unsafe_keywords = ["unlimited risk", "ignore stop loss", "all in"]
        if any(keyword in plan_text.lower() for keyword in unsafe_keywords):
             logger.warning("--- [Green Agent] Plan REJECTED by Safety Check (STPA) ---")
             return GreenAgentResult(
                status="REJECTED",
                feedback="Safety Check Failed: Plan suggests unsafe control actions (e.g., unlimited risk)."
            )

        logger.info("--- [Green Agent] Plan APPROVED ---")
        return GreenAgentResult(
            status="APPROVED",
            feedback="Plan passed all safety and policy checks."
        )

# Singleton instance
green_agent = GreenAgent()
