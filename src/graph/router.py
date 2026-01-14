def risk_router(state):
    """
    Determines if the workflow should proceed to Green Agent (if approved) or loop back for revision.
    """
    if state.get("risk_status") == "REJECTED_REVISE":
        return "execution_analyst" # Send feedback back to planner
    return "green_agent"           # Proceed to System 2 Verification

def green_agent_router(state):
    """
    Determines if the workflow should proceed to execution (if audited) or loop back.
    """
    if state.get("green_agent_status") == "REJECTED":
        return "execution_analyst" # Send feedback back to planner
    return "governed_trader"       # Proceed to trade
