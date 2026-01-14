"""
ADK Agent Adapters for LangGraph Nodes

CRITICAL: These adapters import EXISTING agent instances and wrap them for LangGraph.
Do not create new agent classes here.
"""

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Import EXISTING agent instances from nested structure
from src.agents.data_analyst.agent import data_analyst_agent
from src.agents.risk_analyst.agent import risk_analyst_agent
from src.agents.execution_analyst.agent import execution_analyst_agent
from src.agents.governed_trader.agent import governed_trading_agent

# Session management for ADK agents
session_service = InMemorySessionService()


class AgentResponse:
    """Simple response object to hold agent output."""
    def __init__(self, answer: str = "", function_calls=None):
        self.answer = answer
        self.function_calls = function_calls or []


def run_adk_agent(agent_instance, user_msg: str, session_id: str = "default", user_id: str = "default_user"):
    """
    Wraps the ADK Agent Runner to execute a turn and return the result object.
    Uses the updated Runner.run() API: run(user_id, session_id, new_message)
    """
    import asyncio
    import nest_asyncio
    nest_asyncio.apply()
    
    # Helper to create session asynchronously
    async def ensure_session():
        existing = await session_service.get_session(
            app_name="financial_advisor",
            user_id=user_id,
            session_id=session_id
        )
        if not existing:
            await session_service.create_session(
                app_name="financial_advisor",
                user_id=user_id,
                session_id=session_id
            )
    
    # Ensure session exists before running
    asyncio.get_event_loop().run_until_complete(ensure_session())
    
    runner = Runner(
        agent=agent_instance,
        session_service=session_service,
        app_name="financial_advisor"
    )
    
    # Format the message as Content
    new_message = types.Content(
        role="user",
        parts=[types.Part(text=user_msg)]
    )
    
    # Run and collect events to extract answer
    answer_parts = []
    function_calls = []
    for event in runner.run(user_id=user_id, session_id=session_id, new_message=new_message):
        if hasattr(event, 'content') and event.content:
            for part in event.content.parts:
                if hasattr(part, 'text') and part.text:
                    answer_parts.append(part.text)
                if hasattr(part, 'function_call') and part.function_call:
                    function_calls.append(part.function_call)
    
    return AgentResponse(answer="".join(answer_parts), function_calls=function_calls)




# --- Node Implementations ---

def data_analyst_node(state):
    """Wraps the Data Analyst agent for LangGraph."""
    print("--- [Graph] Calling Data Analyst ---")
    last_msg = state["messages"][-1].content
    res = run_adk_agent(data_analyst_agent, last_msg)
    return {"messages": [("ai", f"Data Analysis: {res.answer}")]}


def risk_analyst_node(state):
    """
    Wraps the Risk Analyst agent for LangGraph.
    Parses output to drive the Refinement Loop.
    """
    print("--- [Graph] Calling Risk Analyst ---")
    last_plan = state["messages"][-1].content
    res = run_adk_agent(risk_analyst_agent, f"Evaluate this plan: {last_plan}")

    # Response is now a JSON string adhering to RiskAssessment schema
    # We parse it to drive the loop logic robustly
    import json
    try:
        data = json.loads(res.answer)
        status = "APPROVED" if data.get("verdict") == "APPROVE" else "REJECTED_REVISE"
        # We return the detailed report as the message text, but keep the JSON structured data for context if needed
        text_output = data.get("detailed_analysis_report", res.answer)
        feedback = data.get("reasoning_summary", "") + "\n" + "\n".join(data.get("detected_unsafe_actions", []))
    except json.JSONDecodeError:
        # Fallback if model fails to produce valid JSON (rare with constrained decoding)
        print("--- [Risk Analyst] WARNING: JSON Decode Error, falling back to heuristic ---")
        text_output = res.answer
        status = "APPROVED"
        if any(k in text_output.lower() for k in ["high risk", "reject", "unsafe", "denied"]):
            status = "REJECTED_REVISE"
        feedback = text_output

    return {
        "messages": [("ai", text_output)],
        "risk_status": status,
        "risk_feedback": feedback
    }


def execution_analyst_node(state):
    """
    Wraps the Execution Analyst (Planner) agent for LangGraph.
    Injects risk feedback if the loop pushed us back here.
    """
    print("--- [Graph] Calling Execution Analyst (Planner) ---")
    user_msg = state["messages"][-1].content

    # INJECT FEEDBACK if the loop pushed us back here
    risk_status = state.get("risk_status")
    green_status = state.get("green_agent_status")

    if risk_status == "REJECTED_REVISE":
        feedback = state.get("risk_feedback")
        user_msg = (
            f"CRITICAL: Your previous strategy was REJECTED by Risk Management.\n"
            f"Feedback: {feedback}\n"
            f"Task: Generate a REVISED, SAFER strategy based on this feedback."
        )
        print("--- [Loop] Injecting Risk Feedback ---")

    elif green_status == "REJECTED":
        feedback = state.get("green_agent_feedback")
        user_msg = (
            f"CRITICAL: Your previous strategy was REJECTED by the Green Agent (Safety Audit).\n"
            f"Feedback: {feedback}\n"
            f"Task: Generate a REVISED, SAFER strategy based on this feedback."
        )
        print("--- [Loop] Injecting Green Agent Feedback ---")

    res = run_adk_agent(execution_analyst_agent, user_msg)

    # Reset status so we can potentially loop again or proceed
    return {"messages": [("ai", res.answer)], "risk_status": "UNKNOWN"}


def governed_trader_node(state):
    """Wraps the Governed Trader agent for LangGraph."""
    print("--- [Graph] Calling Governed Trader ---")
    last_msg = state["messages"][-1].content
    res = run_adk_agent(governed_trading_agent, last_msg)
    return {"messages": [("ai", res.answer)]}
