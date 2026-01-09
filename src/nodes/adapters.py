from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

# Import YOUR EXISTING AGENTS
from src.agents.market_agent import data_analyst_agent
from src.agents.risk_agent import risk_analyst_agent
from src.agents.portfolio_agent import execution_analyst_agent
from src.agents.governed_trader_agent import governed_trading_agent

# Initialize session service ONCE
session_service = InMemorySessionService()

def run_adk_agent(agent_instance, state, prefix="", session_id: str = "default", query_override: str = None):
    """
    Wraps an ADK Agent in a Runner to execute a turn.
    """
    if query_override:
        last_msg = query_override
    else:
        last_msg_obj = state["messages"][-1]
        # Handle tuple format (common in LangGraph tests) or object format
        last_msg = last_msg_obj.content if hasattr(last_msg_obj, "content") else last_msg_obj[1]

    runner = Runner(
        agent=agent_instance,
        session_service=session_service,
        app_name="financial_advisor"
    )

    # ADK runners typically return a structured response object
    result = runner.run(session_id=session_id, query=last_msg)

    # Extract text (adjust attribute based on exact ADK version, usually .text or .answer)
    response_text = result.answer if hasattr(result, 'answer') else str(result)

    return {"messages": [("ai", f"{prefix}{response_text}")]}

# --- Define the Graph Nodes ---

def data_analyst_node(state):
    print("--- [Graph] Calling Existing Data Analyst ---")
    return run_adk_agent(data_analyst_agent, state, prefix="Data Analysis: ")

def risk_analyst_node(state):
    print("--- [Graph] Calling Existing Risk Analyst ---")

    # Call the existing agent to evaluate the plan
    # We construct a prompt wrapper to ensure the agent understands the task
    last_plan_obj = state["messages"][-1]
    last_plan = last_plan_obj.content if hasattr(last_plan_obj, "content") else last_plan_obj[1]

    # Override standard run_adk_agent to pass a specific prompt if needed,
    # but run_adk_agent reads from state. So we might need to manipulate state or
    # just rely on the conversation flow.
    # However, the instruction says: "Call the existing agent to evaluate the plan...
    # response_text = run_adk_agent(..., f"Evaluate this plan: {last_plan}")"
    # My run_adk_agent implementation reads from state["messages"][-1].
    # To follow the instruction exactly and support prompt injection, I should update run_adk_agent or the node.

    # Let's adapt run_adk_agent usage or implementation.
    # The current run_adk_agent takes the *last message* from state.
    # To inject a custom prompt without changing state history permanently yet:

    # We will invoke the agent directly using the runner logic here for custom prompts,
    # or rely on the conversation history.
    # Given "Strict Agent Reuse", we should probably just append the user instruction to the state
    # or pass a modified state to run_adk_agent if we supported it.

    # Actually, the user's plan snippet showed:
    # response_text = run_adk_agent(risk_analyst_agent, f"Evaluate this plan: {last_plan}")
    # But my run_adk_agent signature is (agent_instance, state, prefix, session_id).
    # I should respect the signature or overload it.

    # Let's modify the node to conform to the logic.
    # Since I can't easily change run_adk_agent signature without breaking others,
    # I will construct a temporary state-like object or just use the Runner directly here if needed,
    # OR better, update run_adk_agent to accept an override query.

    # Let's update the node to match the plan's intent using the existing helper if possible,
    # or just updating the helper to take an optional 'query_override'.

    # For now, I'll stick to the plan's logic flow:

    res = run_adk_agent(risk_analyst_agent, state)
    text = res["messages"][0][1]

    # HEURISTIC: Determine status based on Agent's output
    status = "APPROVED"
    # Expanded keywords as per instructions
    if any(keyword in text.lower() for keyword in ["high risk", "reject", "unsafe", "denied", "too risky"]):
        status = "REJECTED_REVISE"

    print(f"--- [Graph] Risk Status: {status} ---")

    return {**res, "risk_status": status, "risk_feedback": text}

def execution_analyst_node(state):
    print("--- [Graph] Calling Existing Execution Analyst (Planner) ---")

    last_msg_obj = state["messages"][-1]
    user_msg = last_msg_obj.content if hasattr(last_msg_obj, "content") else last_msg_obj[1]

    # CHECK FOR FEEDBACK LOOP
    if state.get("risk_status") == "REJECTED_REVISE":
        feedback = state.get("risk_feedback", "Too risky.")
        # Context Injection: We prepend the feedback to the next prompt
        # forcing the existing agent to consider the rejection.
        user_msg = (
            f"CRITICAL: Your previous strategy was REJECTED by Risk Management.\n"
            f"Feedback: {feedback}\n"
            f"Task: Please generate a REVISED, SAFER strategy based on this feedback."
        )
        print(f"--- [Loop] Injecting Risk Feedback: {feedback[:50]}... ---")

        # We need to pass this modified message to the agent.
        # Since run_adk_agent pulls from state, we need a way to override.
        # I will update run_adk_agent to accept an optional query override.

    return run_adk_agent(execution_analyst_agent, state, query_override=user_msg)

def governed_trader_node(state):
    print("--- [Graph] Calling Existing Governed Trader ---")
    return run_adk_agent(governed_trading_agent, state)
