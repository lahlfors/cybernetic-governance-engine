from typing import Dict, Any, List, Optional
import logging
from .ontology import TradingKnowledgeGraph, Constraint

logger = logging.getLogger("GreenAgent.Logic")

class SymbolicReasoner:
    """
    The 'Symbolic' component of the Neuro-Symbolic architecture.
    It evaluates deterministic constraints against a plan.
    """
    def __init__(self, ontology: TradingKnowledgeGraph):
        self.ontology = ontology

    def evaluate_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Audits a structured execution plan.
        Returns a decision dictionary: {"status": "APPROVED" | "REJECTED", "violations": []}
        """
        violations = []
        steps = plan.get("steps", [])

        logger.info(f"Auditing plan with {len(steps)} steps.")

        for step in steps:
            action = step.get("action")
            params = step.get("parameters", {})

            # Map plan actions to ontology scope if needed (simple mapping for now)
            # Assuming step['action'] matches scope keys like 'execute_sell'
            constraints = self.ontology.get_constraints_for_action(action)

            for constraint in constraints:
                if not self._check_constraint(constraint, params):
                    violations.append({
                        "step_id": step.get("id"),
                        "constraint_id": constraint.id,
                        "description": constraint.description,
                        "action": action
                    })

        status = "REJECTED" if violations else "APPROVED"
        logger.info(f"Plan Audit Result: {status} with {len(violations)} violations.")

        return {
            "status": status,
            "violations": violations
        }

    def _check_constraint(self, constraint: Constraint, params: Dict[str, Any]) -> bool:
        """
        Evaluates a single constraint logic against parameters.
        This is a simplified rule engine. In production, use OPA/Rego or Prolog.
        """
        try:
            # SC-1: Approval Token
            if constraint.id == "SC-1":
                # In simulation, we assume 'approval_token' must be present and valid
                return params.get("approval_token") is not None

            # FIN-1: Sell Percentage
            if constraint.id == "FIN-1":
                # params might have 'quantity' and 'portfolio_total'
                quantity = float(params.get("quantity", 0))
                portfolio_total = float(params.get("portfolio_total", 1)) # Prevent div/0
                if portfolio_total == 0: return True
                return (quantity / portfolio_total) <= 0.10

            # Default: If we don't have a specific handler, we assume SAFE for this prototype
            # UNLESS it's a critical safety violation logic we can parse genericly.
            return True

        except Exception as e:
            logger.error(f"Error evaluating constraint {constraint.id}: {e}")
            return False # Fail safe
