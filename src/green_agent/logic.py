"""
Symbolic Logic Engine (Phase 2).
Evaluates logical constraints on the Trading Knowledge Graph.
"""

from typing import List, Tuple
from pydantic import BaseModel
from src.green_agent.ontology import TradingKnowledgeGraph, Asset, Action

class LogicViolation(BaseModel):
    constraint: str
    violation_desc: str

class SymbolicReasoner:
    """
    Mock implementation of a Neuro-Symbolic Reasoner (like DomiKnowS).
    It applies predicate logic to the Knowledge Graph.
    """

    def evaluate(self, kg: TradingKnowledgeGraph) -> List[LogicViolation]:
        violations = []

        assets = {e.ticker: e for e in kg.entities if isinstance(e, Asset)}
        actions = [e for e in kg.entities if isinstance(e, Action)]

        # Constraint 1: High Volatility requires Hedging
        # Logic: FORALL(Action a, Asset s) -> (a.type == Short AND s.vol > 8.0) IMPLIES EXISTS(Action h) WHERE h.type == Hedge
        for action in actions:
            if action.type == "Short":
                target = assets.get(action.target_asset)
                if target and target.volatility_score > 8.0:
                    # Check for hedge
                    has_hedge = any(a.type == "Hedge" for a in actions)
                    if not has_hedge:
                        violations.append(LogicViolation(
                            constraint="HighVolShortHedge",
                            violation_desc=f"Shorting high-volatility asset {target.ticker} (Vol: {target.volatility_score}) without a Hedge action."
                        ))

        # Constraint 2: Illiquid Asset Market Order
        # Logic: FORALL(Action a, Asset s) -> (s.liquidity < 3.0) IMPLIES a.type != "Buy" (Market) -- assuming Buy implies market for this MVP
        for action in actions:
            if action.type in ["Buy", "Sell"]:
                target = assets.get(action.target_asset)
                if target and target.liquidity_score < 3.0:
                     violations.append(LogicViolation(
                            constraint="IlliquidMarketOrder",
                            violation_desc=f"Executing {action.type} on illiquid asset {target.ticker} (Liq: {target.liquidity_score})."
                        ))

        return violations
