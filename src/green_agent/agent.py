import logging
from typing import Dict, Any, List
from .ontology import TradingKnowledgeGraph
from .logic import SymbolicReasoner
from .memory import HistoryAnalyst

logger = logging.getLogger("GreenAgent")

class GreenAgent:
    """
    The 'Proctor' or System 2 Verified Evaluator.
    Orchestrates the Policy, Safety, Logic, and History layers.
    """
    def __init__(self):
        self.ontology = TradingKnowledgeGraph()
        self.logic_engine = SymbolicReasoner(self.ontology)
        self.memory_analyst = HistoryAnalyst()

    def audit_plan(self, plan_data: Dict[str, Any], history: List[Any] = []) -> Dict[str, Any]:
        """
        Main entry point for auditing an execution plan.
        """
        logger.info("Green Agent received plan for audit.")

        # 1. Logic Layer (Symbolic Check)
        logic_result = self.logic_engine.evaluate_plan(plan_data)

        # 2. History Layer (Drift Check)
        history_result = self.memory_analyst.analyze_history(history)

        # 3. Combine Results
        is_approved = (logic_result["status"] == "APPROVED")
        # Warnings from history don't necessarily block, but could trigger Human-in-the-Loop

        feedback = "Plan Approved by Green Agent."
        if not is_approved:
            feedback = f"Plan Rejected. Violations: {logic_result['violations']}"

        return {
            "status": "APPROVED" if is_approved else "REJECTED_REVISE",
            "feedback": feedback,
            "audit_trace": {
                "logic": logic_result,
                "history": history_result
            }
        }

# Global Instance
green_agent = GreenAgent()
