from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from src.green_agent.agent import green_agent

def green_agent_node(state):
    """
    Wraps the Green Agent (Verified Evaluator) for LangGraph.
    Audits the latest plan approved by Risk Analyst.
    """
    print("--- [Graph] Calling Green Agent (Verified Evaluator) ---")

    # CRITICAL FIX: The previous node is Risk Analyst, which outputs a critique/approval.
    # The Green Agent needs to audit the ACTUAL PLAN, which comes from the Execution Analyst (Planner).
    # We search backwards for the last message that likely contains the plan.
    # In this graph, the flow is: Planner (AI) -> Risk (AI) -> Green.
    # So the plan is the *second* to last AI message (or we check for specific markers).

    messages = state["messages"]
    plan_text = ""

    # Iterate backwards to find the Execution Analyst's message.
    # We assume the Execution Analyst is the one before the Risk Analyst.
    # A simple heuristic is to skip the very last message (Risk) and take the one before.
    # Better: Look for the message that *triggered* the Risk Analyst.

    if len(messages) >= 2:
        # messages[-1] is Risk Analyst
        # messages[-2] should be Execution Analyst (the Plan)
        plan_text = messages[-2].content
    else:
        # Fallback (shouldn't happen in valid flow)
        plan_text = messages[-1].content
        print("--- [Green Agent] WARNING: Could not find distinct plan history. Auditing last message. ---")

    result = green_agent.audit_plan(plan_text)

    return {
        "messages": [("ai", f"Green Agent Audit: {result.status}. {result.feedback}")],
        "green_agent_status": result.status,
        "green_agent_feedback": result.feedback
    }
