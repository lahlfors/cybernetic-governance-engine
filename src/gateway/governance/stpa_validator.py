import logging
from typing import Any

from .ontology import Constraint, TradingKnowledgeGraph

logger = logging.getLogger("Gateway.Governance.STPAValidator")

class STPAValidator:
    """
    The 'Symbolic' component of the Neuro-Symbolic architecture.
    It evaluates deterministic constraints (STPA UCAs) against an action.
    Refactored from `SymbolicReasoner`.
    """
    def __init__(self, ontology: TradingKnowledgeGraph = None):
        self.ontology = ontology or TradingKnowledgeGraph()

    def validate(self, action_name: str, params: dict[str, Any]) -> list[str]:
        """
        Validates an action against STPA constraints.
        Returns a list of violation messages. Empty list means SAFE.
        """
        violations = []

        # Get constraints for this action from the ontology
        constraints = self.ontology.get_constraints_for_action(action_name)

        for constraint in constraints:
            if not self._check_constraint(constraint, params):
                violations.append(f"STPA Violation {constraint.id}: {constraint.description}")

        if violations:
            logger.warning(f"⚠️ STPA Validator blocked {action_name}: {violations}")
        else:
            logger.info(f"✅ STPA Validator approved {action_name}")

        return violations

    def _check_constraint(self, constraint: Constraint, params: dict[str, Any]) -> bool:
        """
        Evaluates a single constraint logic against parameters.
        """
        try:
            # SC-1: Approval Token
            if constraint.id == "SC-1":
                # Check if 'approval_token' is present
                return params.get("approval_token") is not None

            # FIN-1: Sell Percentage
            if constraint.id == "FIN-1":
                quantity = float(params.get("quantity", 0))
                # Security Fix: Fail if portfolio_total is missing/zero (Fail Closed)
                portfolio_total = float(params.get("portfolio_total", 0))
                if portfolio_total <= 0:
                     logger.warning(f"Constraint {constraint.id}: Missing or invalid portfolio_total.")
                     return False # Fail Closed
                return (quantity / portfolio_total) <= 0.10

            # FIN-2: Latency Check (UCA-2)
            if constraint.id == "FIN-2":
                # Security Fix: Fail Closed if latency_ms is missing.
                # In production, Gateway should inject this, not the agent.
                if "latency_ms" in params:
                    return float(params["latency_ms"]) <= 200
                else:
                    logger.warning(f"Constraint {constraint.id}: Missing latency_ms metric.")
                    return False # Fail Closed: Cannot verify latency safety

            # Default: If we don't have a specific handler, we assume SAFE
            return True

        except Exception as e:
            logger.error(f"Error evaluating constraint {constraint.id}: {e}")
            # Fail closed on error for safety
            return False
