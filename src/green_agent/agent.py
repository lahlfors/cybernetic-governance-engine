import logging
from typing import Dict, Any, Literal, List
from pydantic import BaseModel
from langchain_core.messages import BaseMessage

from src.governance.client import OPAClient
from src.green_agent.safety_rules import SafetyCheck
from src.green_agent.logic import SymbolicReasoner
from src.green_agent.ontology import TradingKnowledgeGraph, Asset, Action
from src.green_agent.memory import HistoryAnalyst

# Configure logging
logger = logging.getLogger("GreenAgent")

class GreenAgentResult(BaseModel):
    status: Literal["APPROVED", "REJECTED"]
    feedback: str

class GreenAgent:
    """
    The 'Green Agent' acts as a Verified Evaluator (System 2 Verification).
    It audits plans against:
    1. Constitution (OPA Policy)
    2. System Safety (STPA Rules)
    3. Neuro-Symbolic Logic (Phase 2)
    4. Cognitive Continuity (Phase 3)
    """
    def __init__(self):
        self.opa_client = OPAClient()
        self.symbolic_reasoner = SymbolicReasoner()
        self.history_analyst = HistoryAnalyst()

    def _parse_plan_to_kg(self, plan_text: str) -> TradingKnowledgeGraph:
        """
        Heuristic parser to convert text plan to Knowledge Graph.
        In a real implementation, this would be the 'Instructor Agent'.
        """
        entities = []
        plan_lower = plan_text.lower()

        # Heuristic 1: Detect Asset
        if "vix" in plan_lower:
            entities.append(Asset(name="VIX", ticker="VIX", volatility_score=9.0, liquidity_score=8.0))
        elif "gme" in plan_lower: # Added for Logic Test (High Vol, not UCA-2 keyword)
            entities.append(Asset(name="Gamestop", ticker="GME", volatility_score=9.5, liquidity_score=7.0))
        elif "tsla" in plan_lower:
            entities.append(Asset(name="Tesla", ticker="TSLA", volatility_score=7.0, liquidity_score=9.0))
        elif "penny" in plan_lower: # Generic penny stock
            entities.append(Asset(name="PennyStock", ticker="PNY", volatility_score=8.0, liquidity_score=2.0))

        # Heuristic 2: Detect Action
        if "short" in plan_lower:
            target = "VIX" if "vix" in plan_lower else "GME" if "gme" in plan_lower else "TSLA" if "tsla" in plan_lower else "PNY"
            entities.append(Action(name="ShortAction", type="Short", target_asset=target, amount_usd=1000.0))
        elif "buy" in plan_lower:
            target = "PNY" if "penny" in plan_lower else "TSLA"
            entities.append(Action(name="BuyAction", type="Buy", target_asset=target, amount_usd=1000.0))

        # Heuristic 3: Detect Hedge
        if "hedge" in plan_lower:
            entities.append(Action(name="HedgeAction", type="Hedge", target_asset="SPY", amount_usd=500.0))

        return TradingKnowledgeGraph(entities=entities)

    def audit_plan(self, plan_text: str, history: List[BaseMessage] = []) -> GreenAgentResult:
        """
        Audits a proposed plan (textual strategy) against governance rules.
        """
        logger.info("--- [Green Agent] Auditing Plan ---")

        # 1. Structural/Policy Check via OPA
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
                feedback="Governance Policy Violation."
            )

        if policy_decision == "MANUAL_REVIEW":
             return GreenAgentResult(
                status="REJECTED",
                feedback="Policy requires Human Review."
            )

        # 2. System Safety Check (STPA)
        violations_stpa = SafetyCheck.check_unsafe_control_actions(plan_text)
        if violations_stpa:
             logger.warning(f"--- [Green Agent] Plan REJECTED by Safety Check (STPA). ---")
             feedback_lines = [f"- {v.rule_id}: {v.description}" for v in violations_stpa]
             return GreenAgentResult(
                status="REJECTED",
                feedback=f"Safety Check Failed (STPA):\n" + "\n".join(feedback_lines)
            )

        # 3. Neuro-Symbolic Logic Check (Phase 2)
        kg = self._parse_plan_to_kg(plan_text)
        violations_logic = self.symbolic_reasoner.evaluate(kg)
        if violations_logic:
            logger.warning(f"--- [Green Agent] Plan REJECTED by Symbolic Logic. ---")
            feedback_lines = [f"- {v.constraint}: {v.violation_desc}" for v in violations_logic]
            return GreenAgentResult(
                status="REJECTED",
                feedback=f"Logic Check Failed (Neuro-Symbolic):\n" + "\n".join(feedback_lines)
            )

        # 4. Cognitive Continuity Check (Phase 3)
        if history:
            violations_drift = self.history_analyst.analyze_history(history)
            if violations_drift:
                logger.warning(f"--- [Green Agent] Plan REJECTED by History Analyst (Drift). ---")
                feedback_lines = [f"- {v.drift_type}: {v.description}" for v in violations_drift]
                return GreenAgentResult(
                    status="REJECTED",
                    feedback=f"History Check Failed (Cognitive Continuity):\n" + "\n".join(feedback_lines)
                )

        logger.info("--- [Green Agent] Plan APPROVED ---")
        return GreenAgentResult(
            status="APPROVED",
            feedback="Plan passed all safety, policy, logic, and history checks."
        )

# Singleton instance
green_agent = GreenAgent()
