"""
ADK Agent Adapters for LangGraph Nodes

Uses Dependency Injection pattern to allow mocking during tests.
"""

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# LangSmith Deep Integration
try:
    from langsmith import traceable
except ImportError:
    # No-op decorator if langsmith is not installed (e.g., during minimal tests)
    def traceable(**kwargs):
        def decorator(func):
            return func
        return decorator

# Import Factory Functions
from src.governed_financial_advisor.agents.data_analyst.agent import create_data_analyst_agent
from src.governed_financial_advisor.agents.execution_analyst.agent import create_execution_analyst_agent
from src.governed_financial_advisor.agents.governed_trader.agent import create_governed_trader_agent

# Session management for ADK agents
session_service = InMemorySessionService()

logger = logging.getLogger("Graph.Adapters")




def get_valid_last_message(state) -> str:
    """Retrieves the last non-empty message content from the state."""
    messages = state.get("messages", [])
    for msg in reversed(messages):
        content = getattr(msg, "content", "")
        # Handle simple string content
        if isinstance(content, str) and content.strip():
            return content
        # Handle list content (multi-modal or parts)
        if isinstance(content, list) and content:
             return content # Pass complex content through
    return "No content available."

def get_market_data_from_history(state) -> str | None:
    """
    Scans the conversation history for the most recent Data Analyst output.
    Returns the content if found, or None.
    """
    messages = state.get("messages", [])
    for msg in reversed(messages):
        content = getattr(msg, "content", "")
        if isinstance(content, str) and "Data Analysis:" in content:
            return content
    return None

# --- Dependency Injection Infrastructure ---

_agent_registry = {}
_agent_cache = {}

def get_agent(name: str, factory: Callable[[], Any]) -> Any:
    """
    Retrieves an agent instance.
    If a mock is registered in _agent_registry, returns that.
    Otherwise, creates (and caches) the real agent using the factory.
    """
    # 1. Check for overrides/mocks (Transient)
    if name in _agent_registry:
        return _agent_registry[name]

    # 2. Check cache (Singleton)
    if name not in _agent_cache:
        logger.info(f"Creating new agent instance for: {name}")
        _agent_cache[name] = factory()

    return _agent_cache[name]

def inject_agent(name: str, instance: Any):
    """Injects an agent instance (mock) for testing."""
    _agent_registry[name] = instance

def clear_agent_cache():
    """Clears the agent cache and registry."""
    _agent_registry.clear()
    _agent_cache.clear()

class AgentResponse:
    """Simple response object to hold agent output."""
    def __init__(self, answer: str = "", function_calls=None):
        self.answer = answer
        self.function_calls = function_calls or []

@traceable(run_type="chain", name="ADK Agent Runner")
def run_adk_agent(agent_instance, user_msg: str, session_id: str = "default", user_id: str = "default_user"):
    """
    Wraps the ADK Agent Runner to execute a turn and return the result object.
    Uses the updated Runner.run() API: run(user_id, session_id, new_message)
    """
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
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Use nest_asyncio to allow re-entrant loop if needed
    loop.run_until_complete(ensure_session())

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
    try:
        for event in runner.run(user_id=user_id, session_id=session_id, new_message=new_message):
            if hasattr(event, 'content') and event.content:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        answer_parts.append(part.text)
                    if hasattr(part, 'function_call') and part.function_call:
                        function_calls.append(part.function_call)
    except Exception as e:
        logger.error(f"Error running ADK agent: {e}")
        return AgentResponse(answer=f"Error: {e!s}")

    return AgentResponse(answer="".join(answer_parts), function_calls=function_calls)


# --- Node Implementations ---

def data_analyst_node(state):
    """Wraps the Data Analyst agent for LangGraph."""
    print("--- [Graph] Calling Data Analyst ---")
    agent = get_agent("data_analyst", create_data_analyst_agent)
    last_msg = get_valid_last_message(state)
    res = run_adk_agent(agent, last_msg)
    return {"messages": [("ai", f"Data Analysis: {res.answer}")]}


def execution_analyst_node(state):
    """
    Wraps the Execution Analyst (Planner) agent for LangGraph.
    Injects risk feedback if the loop pushed us back here.
    Parses the JSON output to populate 'execution_plan_output'.
    """
    print("--- [Graph] Calling Execution Analyst (Planner) ---")
    agent = get_agent("execution_analyst", create_execution_analyst_agent)
    user_msg = get_valid_last_message(state)

    # 0. DATA CHECK: We need market data to form a specific strategy.
    # We now look back in history, not just the immediate last message.
    market_data_msg = get_market_data_from_history(state)
    
    if not market_data_msg:
        print("--- [Graph] Missing Market Data -> Asking User for Ticker ---")
        return {
            "messages": [("ai", "I can certainly help you develop a trading strategy. **Which stock ticker** would you like me to research first?")],
            "next_step": "FINISH",
            "risk_status": "UNKNOWN",
            "execution_plan_output": None
        }

    # 1. PROFILE CHECK: DISABLED to allow Agent to extract it from context
    # if not state.get("risk_attitude") or not state.get("investment_period"):
    #     print("--- [Graph] Missing Profile -> Asking User ---")
    #     msg = (
    #         "I have the market analysis. To tailor the strategy, please select your **Risk Tolerance** and **Time Frame**:\n\n"
    #         "Stock trading strategies generally fall into three levels of aggressiveness:\n"
    #         "- **Aggressive** (High Risk, High Growth): Maximizes returns with higher volatility exposure.\n"
    #         "- **Moderate** (Balanced Risk/Reward): Balances growth and capital preservation.\n"
    #         "- **Conservative** (Low Risk, Capital Preservation): Prioritizes stability and lower turnover.\n\n"
    #         "Please copy and paste your choice (e.g., 'Aggressive') and specify your **Time Frame** (Short, Medium, or Long)."
    #     )
    #     return {
    #         "messages": [("ai", msg)],
    #         "next_step": "FINISH",
    #         "risk_status": "UNKNOWN",
    #         "execution_plan_output": None
    #     }

    # INJECT FEEDBACK if the loop pushed us back here
    if state.get("risk_status") == "REJECTED_REVISE":
        feedback = state.get("risk_feedback")
        user_msg = (
            f"CRITICAL: Your previous strategy was REJECTED by Risk Management.\n"
            f"Feedback: {feedback}\n"
            f"Task: Generate a REVISED, SAFER strategy based on this feedback."
        )
        print("--- [Loop] Injecting Risk Feedback ---")

    # PIPELINE LOGIC: Construct the prompt with context
    else:
        # Check if we already have risk attitude in state, if so, mention it.
        risk = state.get("risk_attitude", "moderate") # Default to moderate if unknown, or let agent ask
        period = state.get("investment_period", "medium-term")

        # If the user just asked for a strategy (e.g. "Recommend a strategy"), we want to
        # include the market data in the context so the agent doesn't hallucinate or ask for it again.
        
        # If the last message IS the data analysis, user_msg is already set to it.
        # If the last message is a user prompt, we assume it's the trigger.
        
        user_msg = (
            f"CONTEXT: The following is the Market Analysis we have already performed.\n"
            f"USER PROFILE: Risk Attitude: {risk}, Horizon: {period}\n"
            f"CURRENT REQUEST: {user_msg}\n"
            f"TASK: Generate a suggested set of specific trading strategies (Execution Plan) based on the analysis below.\n"
            f"Ensure the strategies are concrete, actionable, and aligned with the Risk/Time profile.\n\n"
            f"--- MARKET ANALYSIS ---\n"
            f"{market_data_msg}"
        )
        print("--- [Pipeline] Auto-prompting Strategy Generation with Context ---")

    res = run_adk_agent(agent, user_msg)

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

    # Format the output for the user
    if plan_output and isinstance(plan_output, dict):
        steps_text = "\n".join([f"{i+1}. {s.get('action')} ({s.get('description')})" for i, s in enumerate(plan_output.get("steps", []))])
        final_response = (
            f"### Executive Plan: {plan_output.get('strategy_name', 'Custom Strategy')}\n\n"
            f"**Rationale:** {plan_output.get('rationale')}\n\n"
            f"**Steps:**\n{steps_text}\n\n"
            f"**Risk Factors:** {', '.join(plan_output.get('risk_factors', []))}\n\n"
            f"*(Generated by System 4 Planner)*\n\n"
            f"**Would you like me to execute this trade or implement this plan?**"
        )
    else:
        final_response = res.answer

    # Reset status so we can potentially loop again or proceed
    return {
        "messages": [("ai", final_response)],
        "risk_status": "UNKNOWN",
        "execution_plan_output": plan_output,
        # Update State from Plan (Context Extraction)
        "risk_attitude": plan_output.get("user_risk_attitude") if plan_output else None,
        "investment_period": plan_output.get("user_investment_period") if plan_output else None
    }


def governed_trader_node(state):
    """Wraps the Governed Trader agent for LangGraph."""
    print("--- [Graph] Calling Governed Trader ---")
    agent = get_agent("governed_trader", create_governed_trader_agent)
    last_msg = get_valid_last_message(state)
    res = run_adk_agent(agent, last_msg)
    return {"messages": [("ai", res.answer)]}
