def risk_router(state):
    """
    Determines if the workflow should proceed to execution or loop back for revision.
    """
    if state.get("risk_status") == "REJECTED_REVISE":
        return "execution_analyst" # Send feedback back to planner
    return "governed_trader"       # Proceed to trade
