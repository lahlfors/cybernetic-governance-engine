from src.green_agent.agent import green_agent

def green_agent_node(state):
    """
    Wraps the Green Agent (Verified Evaluator) for LangGraph.
    Audits the latest plan approved by Risk Analyst.
    """
    print("--- [Graph] Calling Green Agent (Verified Evaluator) ---")

    # We assume the last message or context contains the plan to be audited.
    # Typically, this would be the Risk Analyst's approved output or the Planner's original plan.
    # For now, we take the last message content.
    last_msg = state["messages"][-1].content

    result = green_agent.audit_plan(last_msg)

    return {
        "messages": [("ai", f"Green Agent Audit: {result.status}. {result.feedback}")],
        "green_agent_status": result.status,
        "green_agent_feedback": result.feedback
    }
