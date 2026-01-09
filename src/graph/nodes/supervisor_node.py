from langchain_core.runnables.config import RunnableConfig
from src.graph.nodes.adapters import run_adk_agent, get_session_id
from src.agents.root_agent import root_agent

def supervisor_node(state, config: RunnableConfig):
    print("--- [Graph] Supervisor (Root Agent) ---")
    last_msg = state["messages"][-1].content
    session_id = get_session_id(config)

    # 1. Run Root Agent (The "Brain")
    response = run_adk_agent(root_agent, last_msg, session_id=session_id)

    # 2. Intercept 'route_request' Tool Call (The "Signal")
    next_step = "FINISH"
    agent_text = response.answer or ""

    if hasattr(response, 'function_calls') and response.function_calls:
        for call in response.function_calls:
            if call.name == "route_request":
                # Extract the target argument
                target = call.args.get("target") or call.args.get("request_type")
                print(f"--- [Graph] Intercepted Route Signal: {target} ---")

                if "data" in target:
                    next_step = "data_analyst"
                elif "execution" in target:
                    next_step = "execution_analyst"
                elif "risk" in target:
                    next_step = "risk_analyst"
                elif "trade" in target:
                    next_step = "governed_trader"

    # Return the agent's text (e.g. "I'll ask the analyst...") AND the routing signal
    return {"messages": [("ai", agent_text)], "next_step": next_step}
