"""
Supervisor Node: Root Agent with Route Interception

CRITICAL: This replaces a generic LLM node. It uses the root_agent to decide
routing by intercepting its route_request tool call.
"""

from src.graph.nodes.adapters import run_adk_agent
from src.agents.financial_advisor.agent import root_agent
from src.governance.stpa import ControlLoop
from src.graph.state import AgentState # Need this for type checking if filtering keys

def supervisor_node(state):
    """
    The Supervisor Node runs the root_agent (the "Brain") and intercepts
    the route_request tool call (the "Signal") to determine next steps.
    It also manages and persists the user's risk profile and sets STPA context.
    """
    print("--- [Graph] Supervisor (Root Agent) ---")

    # --- State Management: Extract and persist user profile ---
    updated_state = state.copy()

    # Safely get last message
    last_msg = state["messages"][-1]
    # Check if last_msg is a tuple or object. State definition says BaseMessage,
    # but langgraph usually handles tuples like ("user", "text") if using add_messages.
    if isinstance(last_msg, tuple):
        last_msg_text = last_msg[1].lower()
    else:
        last_msg_text = getattr(last_msg, "content", "").lower()

    # Check for risk attitude in the last message
    if any(term in last_msg_text for term in ["conservative", "moderate", "aggressive"]):
        if "conservative" in last_msg_text:
            updated_state["risk_attitude"] = "conservative"
        elif "moderate" in last_msg_text:
            updated_state["risk_attitude"] = "moderate"
        elif "aggressive" in last_msg_text:
            updated_state["risk_attitude"] = "aggressive"
        print(f"--- [State] Updated risk_attitude: {updated_state['risk_attitude']} ---")

    # Check for investment period in the last message
    if any(term in last_msg_text for term in ["short-term", "mid-term", "long-term"]):
        if "short-term" in last_msg_text:
            updated_state["investment_period"] = "short-term"
        elif "mid-term" in last_msg_text:
            updated_state["investment_period"] = "mid-term"
        elif "long-term" in last_msg_text:
            updated_state["investment_period"] = "long-term"
        print(f"--- [State] Updated investment_period: {updated_state['investment_period']} ---")

    # --- Context Augmentation: Prepend user profile to the message ---
    augmented_message = last_msg_text
    if updated_state.get("risk_attitude") and updated_state.get("investment_period"):
        profile_context = (
            f"User Profile Context:\n"
            f"- Risk Attitude: {updated_state['risk_attitude']}\n"
            f"- Investment Period: {updated_state['investment_period']}\n\n"
        )
        augmented_message = f"{profile_context}User Request: {last_msg_text}"

    # 1. Run Root Agent (The "Brain")
    response = run_adk_agent(root_agent, augmented_message)

    # 2. Intercept 'route_request' Tool Call (The "Signal")
    next_step = "FINISH"
    stpa_metadata = None
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
                    # Initialize STPA Loop Context for Execution
                    stpa_metadata = ControlLoop(
                        id="LOOP-EXEC-001",
                        name="Execution Planning Loop",
                        controller="ExecutionAnalyst",
                        controlled_process="Financial Market / Exchange",
                        control_actions=["propose_trade", "analyze_market"],
                        feedback_mechanism="Risk Feedback & Market Data"
                    )
                elif "risk" in target_lower:
                    next_step = "risk_analyst"
                elif "trade" in target_lower:
                    next_step = "governed_trader"
                    # Initialize STPA Loop Context for Trading (Hot Path)
                    stpa_metadata = ControlLoop(
                        id="LOOP-TRADE-001",
                        name="Trade Execution Loop",
                        controller="GovernedTrader",
                        controlled_process="Exchange API",
                        control_actions=["execute_order"],
                        feedback_mechanism="Order Confirmation & Balance Update"
                    )
                elif "human" in target_lower or "review" in target_lower:
                    next_step = "human_review"

    # 3. Return updated state and routing signal
    # We must return the 'updated_state' dictionary, not the original 'state'
    updated_state["messages"] = state["messages"] + [("ai", agent_text)]
    updated_state["next_step"] = next_step

    if stpa_metadata:
        updated_state["control_loop_metadata"] = stpa_metadata
        print(f"--- [STPA] Initialized Loop: {stpa_metadata.name} ---")

    # Remove keys that are not part of AgentState to avoid errors
    final_output = {k: v for k, v in updated_state.items() if k in AgentState.__annotations__}

    return final_output
