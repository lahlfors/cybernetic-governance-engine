"""
Cognitive Continuity Layer (Phase 3).
This module implements the 'History Analyst' which uses State Space Models (Mamba)
or heuristics to detect slow-moving risks (Drift) over long horizons.
"""

from typing import List, Literal
from pydantic import BaseModel
from langchain_core.messages import BaseMessage

class DriftViolation(BaseModel):
    drift_type: str
    description: str
    severity: Literal["HIGH", "CRITICAL"]

class HistoryAnalyst:
    """
    Analyzes the agent's conversation history to detect 'Boiling Frog' attacks
    or semantic drift that single-turn checks miss.

    Future State: This will wrap a Mamba-2.8B model.
    Current State: Heuristic aggregation.
    """

    def analyze_history(self, history: List[BaseMessage]) -> List[DriftViolation]:
        violations = []

        # Heuristic 1: Cumulative Leverage Creep (The "Boiling Frog")
        # Check if leverage/risk keywords are appearing with increasing frequency
        # or if the user is repeatedly pushing for riskier assets after mild pushback.

        # We look at the last 10 turns
        recent_history = history[-10:] if len(history) > 10 else history

        risk_counter = 0
        for msg in recent_history:
            content = str(msg.content).lower()
            if "leverage" in content or "margin" in content or "borrow" in content:
                risk_counter += 1

        # If > 50% of recent messages discuss leverage, flag as drift.
        # This catches a user who asks "Can I use 2x?", "How about 3x?", "Just 4x?"
        if len(recent_history) >= 4 and risk_counter >= (len(recent_history) / 2):
            violations.append(DriftViolation(
                drift_type="CumulativeRiskCreep",
                description="Cognitive Continuity Warning: Persistent pattern of increasing risk requests detected over recent history.",
                severity="HIGH"
            ))

        return violations
