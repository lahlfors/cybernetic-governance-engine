"""
ADK Agent Adapters for LangGraph Nodes

CRITICAL: These adapters import EXISTING agent instances and wrap them for LangGraph.
Do not create new agent classes here.
"""

import json
import logging
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

logger = logging.getLogger("Graph.Adapters")

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
    print(f"--- [Graph] Data Analyst Input: {last_msg[:100]}... ---")
    
    res = run_adk_agent(data_analyst_agent, last_msg)
    
    print(f"--- [Graph] Data Analyst Completed. Response length: {len(res.answer)} chars ---")
    print(f"--- [Graph] Data Analyst Response preview: {res.answer[:200]}... ---")
    
    return {"messages": [("ai", f"Data Analysis: {res.answer}")]}


def risk_analyst_node(state):
    """
    Wraps the Risk Analyst agent for LangGraph.
    Parses output to drive the Refinement Loop.
    """
    print("--- [Graph] Calling Risk Analyst ---")
    last_plan = state["messages"][-1].content
    res = run_adk_agent(risk_analyst_agent, f"Evaluate this plan: {last_plan}")

    # Heuristic: Parse the Risk Agent's text output to drive the Loop
    text = res.answer
    status = "APPROVED"
    if any(k in text.lower() for k in ["high risk", "reject", "unsafe", "denied"]):
        status = "REJECTED_REVISE"

    return {
        "messages": [("ai", text)],
        "risk_status": status,
        "risk_feedback": text
    }


def execution_analyst_node(state):
    """
    Wraps the Execution Analyst (Planner) agent for LangGraph.
    Injects risk feedback if the loop pushed us back here.
    Parses the JSON output to populate 'execution_plan_output'.
    """
    print("--- [Graph] Calling Execution Analyst (Planner) ---")
    user_msg = state["messages"][-1].content

    # INJECT FEEDBACK if the loop pushed us back here
    if state.get("risk_status") == "REJECTED_REVISE":
        feedback = state.get("risk_feedback")
        user_msg = (
            f"CRITICAL: Your previous strategy was REJECTED by Risk Management.\n"
            f"Feedback: {feedback}\n"
            f"Task: Generate a REVISED, SAFER strategy based on this feedback."
        )
        print("--- [Loop] Injecting Risk Feedback ---")

    res = run_adk_agent(execution_analyst_agent, user_msg)

    # PARSE JSON Output
    plan_output = None
    try:
        # The agent is configured to return JSON, so res.answer should be a JSON string.
        # We try to parse it.
        # Handle markdown blocks ```json ... ``` if present
        json_str = res.answer
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
             json_str = json_str.split("```")[1].split("```")[0].strip()

        plan_output = json.loads(json_str)
        logger.info(f"✅ Parsed Execution Plan: {plan_output.get('plan_id', 'unknown')}")

    except Exception as e:
        logger.warning(f"⚠️ Failed to parse Execution Plan JSON: {e}. Passing raw text.")
        # Fallback: create a dummy plan wrapper around the text so Safety Node doesn't crash completely
        plan_output = {
            "steps": [],
            "reasoning": res.answer,
            "error": "Failed to parse JSON plan"
        }

    # Reset status so we can potentially loop again or proceed
    return {
        "messages": [("ai", res.answer)],
        "risk_status": "UNKNOWN",
        "execution_plan_output": plan_output
    }


def governed_trader_node(state):
    """Wraps the Governed Trader agent for LangGraph."""
    print("--- [Graph] Calling Governed Trader ---")
    last_msg = state["messages"][-1].content
    res = run_adk_agent(governed_trading_agent, last_msg)
    return {"messages": [("ai", res.answer)]}
