from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from src.green_agent.agent import green_agent

def green_agent_node(state):
    """
    Wraps the Green Agent (Verified Evaluator) for LangGraph.
    Audits the latest plan approved by Risk Analyst.
    """
    print("--- [Graph] Calling Green Agent (Verified Evaluator) ---")

    messages = state["messages"]
    plan_text = ""

    # Iterate backwards to find the Execution Analyst's message.
    if len(messages) >= 2:
        # messages[-1] is Risk Analyst
        # messages[-2] should be Execution Analyst (the Plan)
        plan_text = messages[-2].content
    else:
        # Fallback (shouldn't happen in valid flow)
        plan_text = messages[-1].content
        print("--- [Green Agent] WARNING: Could not find distinct plan history. Auditing last message. ---")

    # Pass full history to audit_plan for Cognitive Continuity (Phase 3)
    result = green_agent.audit_plan(plan_text, history=messages)

    return {
        "messages": [("ai", f"Green Agent Audit: {result.status}. {result.feedback}")],
        "green_agent_status": result.status,
        "green_agent_feedback": result.feedback
    }
