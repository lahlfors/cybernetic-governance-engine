"""
Unit Tests for Risk Router Logic

Tests the conditional routing logic that drives the Refinement Loop:
- APPROVED -> governed_trader
- REJECTED_REVISE -> execution_analyst (loop back)
- UNKNOWN -> governed_trader (default)
"""



def risk_router(state: dict) -> str:
    """
    Extracted router logic from graph.py for isolated testing.
    In production, this is defined inline in create_graph().
    """
    if state.get("risk_status") == "REJECTED_REVISE":
        return "execution_analyst"
    return "governed_trader"


class TestRiskRouter:
    """Unit tests for the risk_router decision function."""

    def test_risk_router_approved(self):
        """When risk status is APPROVED, route to governed_trader."""
        state = {
            "risk_status": "APPROVED",
            "risk_feedback": "Trade meets all risk criteria.",
            "messages": [],
        }
        assert risk_router(state) == "governed_trader"

    def test_risk_router_rejected_revise(self):
        """When risk status is REJECTED_REVISE, loop back to execution_analyst."""
        state = {
            "risk_status": "REJECTED_REVISE",
            "risk_feedback": "High risk: Portfolio concentration exceeds 30%.",
            "messages": [],
        }
        assert risk_router(state) == "execution_analyst"

    def test_risk_router_unknown(self):
        """When risk status is UNKNOWN, default to governed_trader."""
        state = {
            "risk_status": "UNKNOWN",
            "risk_feedback": None,
            "messages": [],
        }
        assert risk_router(state) == "governed_trader"

    def test_risk_router_missing_status(self):
        """When risk_status is missing from state, default to governed_trader."""
        state = {
            "messages": [],
        }
        assert risk_router(state) == "governed_trader"

    def test_risk_router_empty_state(self):
        """Router handles empty state gracefully."""
        state = {}
        assert risk_router(state) == "governed_trader"
