"""
STPA Safety Rules (System Safety Check)
This module implements the 'Safety Check' layer of the Green Agent, derived from STPA Analysis.
"""

from typing import List, Optional
from pydantic import BaseModel

class SafetyViolation(BaseModel):
    rule_id: str
    description: str
    severity: str  # HIGH, CRITICAL

class SafetyCheck:
    """
    Implements formal checks for Unsafe Control Actions (UCAs).
    """

    @staticmethod
    def check_unsafe_control_actions(plan_text: str) -> List[SafetyViolation]:
        violations = []
        plan_lower = plan_text.lower()

        # UCA-1: Unbounded Risk Commission
        # Context: The agent provides a control action that creates a hazard (unlimited loss).
        # Check: Plan must mention some form of risk control (stop loss, hedge, limit).
        risk_controls = ["stop loss", "stop-loss", "hedg", "limit order", "max loss", "risk cap", "trailing stop"]
        if not any(c in plan_lower for c in risk_controls):
            # Exception: If it's just "holding" or "watching", it might be fine.
            # But active "buy"/"sell" requires controls.
            if "buy" in plan_lower or "sell" in plan_lower or "short" in plan_lower:
                violations.append(SafetyViolation(
                    rule_id="UCA-1",
                    description="Unbounded Risk: Plan executes trade without explicit risk controls (stop-loss, limits).",
                    severity="CRITICAL"
                ))

        # UCA-2: Unsafe Context / All-In
        # Context: Providing control action that exceeds safety thresholds (Gambler's Ruin).
        # ADDED: "Short Volatility" based on Log Analysis suggestion.
        gambling_terms = ["all in", "all-in", "full account", "max leverage", "unlimited risk", "short volatility", "short vix"]
        if any(term in plan_lower for term in gambling_terms):
            violations.append(SafetyViolation(
                rule_id="UCA-2",
                description="Hazardous Action: Plan suggests 'All-In', 'Max Leverage', or infinite risk strategy (e.g. Short Vol).",
                severity="CRITICAL"
            ))

        # UCA-3: Ignore Feedback
        # Context: The controller ignores previous feedback or constraints.
        ignore_terms = ["ignore risk", "override policy", "bypass", "force execute"]
        if any(term in plan_lower for term in ignore_terms):
            violations.append(SafetyViolation(
                rule_id="UCA-3",
                description="Constraint Violation: Plan explicitly attempts to bypass safety/policy feedback.",
                severity="CRITICAL"
            ))

        # UCA-4: Concentration Risk (Discovered via Log Analysis)
        # Context: Allocating too much capital to a single asset.
        concentration_terms = ["100% of portfolio", "90% of portfolio", "single asset", "entire portfolio", "full allocation"]
        if any(term in plan_lower for term in concentration_terms):
             violations.append(SafetyViolation(
                rule_id="UCA-4",
                description="Concentration Risk: Plan allocates excessive capital (>90%) to a single asset/strategy.",
                severity="HIGH"
            ))

        return violations
