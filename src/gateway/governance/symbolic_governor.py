"""
Symbolic Governor (Neuro-Symbolic Governance Layer)

This component implements the "SR 11-7 Wrapper" around the Neural components.
It enforces deterministic, symbolic rules that cannot be bypassed by the probabilistic
neural networks.

Responsibilities:
1. SR 11-7 Compliance: Enforce hard constraints (e.g., Confidence >= 0.95, CBF Safety).
2. ISO 42001 Compliance: Ensure process transparency, logging, and human oversight (Consensus).
3. Cybernetic Stability: Prevent actions that violate safety boundaries.
"""

import logging
from typing import Any, Dict

from src.gateway.core.policy import OPAClient
from src.governed_financial_advisor.governance.safety import ControlBarrierFunction
from src.governed_financial_advisor.governance.consensus import ConsensusEngine

logger = logging.getLogger("SymbolicGovernor")

class GovernanceError(Exception):
    """Raised when a symbolic rule is violated."""
    pass

class SymbolicGovernor:
    def __init__(
        self,
        opa_client: OPAClient,
        safety_filter: ControlBarrierFunction,
        consensus_engine: ConsensusEngine
    ):
        self.opa_client = opa_client
        self.safety_filter = safety_filter
        self.consensus_engine = consensus_engine

    async def govern(self, tool_name: str, params: Dict[str, Any]) -> None:
        """
        Orchestrates the governance checks.
        Raises GovernanceError if any check fails.
        """
        logger.info(f"⚖️ Symbolic Governor evaluating: {tool_name}")

        # 1. SR 11-7: "Conceptual Soundness" / Deterministic Rules
        # Rule: "If confidence interval < 95%, do not execute trade."
        # This applies specifically to trade execution.
        if tool_name == "execute_trade":
            confidence = params.get("confidence", 0.0)
            if confidence < 0.95:
                raise GovernanceError(
                    f"SR 11-7 Violation: Model Confidence {confidence} < 0.95. Action Rejected."
                )

            # 2. SR 11-7 / Cybernetic Stability: Control Barrier Function (Safety)
            # Checks if the action violates safety boundaries (e.g. bankruptcy).
            cbf_result = self.safety_filter.verify_action(tool_name, params)
            if cbf_result.startswith("UNSAFE"):
                raise GovernanceError(f"Safety Violation (CBF): {cbf_result}")

        # 3. ISO 42001: Policy Compliance (OPA)
        # Checks organizational policies (e.g. "No trading in restricted regions").
        # This is a "Process" check.
        # We construct the payload for OPA.
        opa_payload = params.copy()
        opa_payload["action"] = tool_name

        policy_decision = await self.opa_client.evaluate_policy(opa_payload)
        if policy_decision == "DENY":
            raise GovernanceError("ISO 42001 Policy Violation: OPA Denied Action.")
        if policy_decision == "MANUAL_REVIEW":
            raise GovernanceError("ISO 42001 Policy Check: Manual Review Required.")

        # 4. ISO 42001: Human Oversight / Consensus (Adaptive Compute)
        # For high-stakes actions, trigger multi-agent consensus.
        if tool_name == "execute_trade":
            amount = params.get("amount", 0.0)
            symbol = params.get("symbol", "UNKNOWN")

            consensus = await self.consensus_engine.check_consensus(tool_name, amount, symbol)
            if consensus["status"] == "REJECT":
                raise GovernanceError(f"Consensus Rejection: {consensus['reason']}")
            # ESCALATE is currently treated as a block in the original code,
            # or could be allowed if human loop is implemented.
            # Here we will treat ESCALATE as a GovernanceError for automation safety.
            if consensus["status"] == "ESCALATE":
                raise GovernanceError(f"Consensus Escalation: {consensus['reason']}")

        logger.info(f"✅ Symbolic Governor Approved: {tool_name}")
