"""
Supervisor Node: Root Agent with Route Interception

CRITICAL: This replaces a generic LLM node. It uses the root_agent to decide
routing by intercepting its route_request tool call.
"""

from src.graph.nodes.adapters import run_adk_agent
from src.agents.financial_advisor.agent import root_agent


def supervisor_node(state):
    """
    The Supervisor Node runs the root_agent (the "Brain") and intercepts
    the route_request tool call (the "Signal") to determine next steps.
    """
    print("--- [Graph] Supervisor (Root Agent) ---")
    last_msg = state["messages"][-1].content

    # 1. Run Root Agent (The "Brain")
    response = run_adk_agent(root_agent, last_msg)

    # 2. Intercept 'route_request' Tool Call (The "Signal")
    next_step = "FINISH"
    agent_text = response.answer or ""

    if hasattr(response, 'function_calls') and response.function_calls:
        for call in response.function_calls:
            if call.name == "route_request":
                # Extract the target argument
                target = call.args.get("target") or call.args.get("request_type") or ""
                print(f"--- [Graph] Intercepted Route Signal: {target} ---")

                target_lower = target.lower()
                if "data" in target_lower:
                    next_step = "data_analyst"
                elif "execution" in target_lower:
                    next_step = "execution_analyst"
                elif "risk" in target_lower:
                    next_step = "risk_analyst"
                elif "trade" in target_lower:
                    next_step = "governed_trader"
                elif "human" in target_lower or "review" in target_lower:
                    next_step = "human_review"

    # Return the agent's text (e.g. "I'll ask the analyst...") AND the routing signal
    return {"messages": [("ai", agent_text)], "next_step": next_step}
