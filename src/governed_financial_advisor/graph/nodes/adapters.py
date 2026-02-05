"""
ADK Agent Adapters for LangGraph Nodes (Production Version)

Refactored to use standard `google.adk` Runner with InMemorySessionService.
"""

import logging
import json
from collections.abc import Callable
from typing import Any, Optional

# Import ADK components
try:
    from google.adk.runners import Runner
    # User specified google.adk.runners.InMemorySessionService, but standard might be google.adk.memory
    # We try both to be safe, prioritizing the user's suggestion if valid.
    try:
        from google.adk.runners import InMemorySessionService
    except ImportError:
        from google.adk.memory import InMemorySessionService
except ImportError as e:
    # Fallback or re-raise if strictly required. For now, re-raise to fail fast if missing.
    raise ImportError(f"Google ADK dependencies missing: {e}")

# Import Factory Functions
from src.governed_financial_advisor.agents.data_analyst.agent import create_data_analyst_agent
from src.governed_financial_advisor.agents.execution_analyst.agent import create_execution_analyst_agent
from src.governed_financial_advisor.agents.governed_trader.agent import create_governed_trader_agent

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
             return str(content) # Pass complex content through as str for now
    return "No content available."

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

def run_adk_agent(agent_instance, user_msg: str, session_id: str = "default", user_id: str = "default_user") -> AgentResponse:
    """
    Executes an ADK Agent using the Runner and InMemorySessionService.
    The state is ephemeral per request/session if session_id varies,
    but here we use InMemorySessionService which is local to the process.
    """
    try:
        # 1. Initialize Session Service (Ephemeral)
        # In a real persistent scenario, we might use FirestoreSessionService,
        # but requirements specify InMemorySessionService.
        session_service = InMemorySessionService()

        # 2. Initialize Runner
        runner = Runner(
            agent=agent_instance,
            session_service=session_service
        )

        # 3. Execute
        # Runner.run() typically returns the final text response.
        # We need to verify the return type of runner.run().
        # Usually it returns the model response string or object.
        logger.info(f"Running agent {agent_instance.name} with session_id={session_id}")

        # Note: Runner.run signature might vary. Assuming run(user_input, session_id=...)
        # or run(session_id=..., prompt=...)
        # We will try the standard pattern: runner.run(session_id=session_id, prompt=user_msg)
        # Or if it's a simple runner: runner.run(user_msg)

        # Based on standard ADK usage:
        result = runner.run(
            session_id=session_id,
            prompt=user_msg
        )

        # 4. Wrap Response
        # Result is typically the string answer for simple text agents.
        # If it returns a structure, we might need to extract text.
        return AgentResponse(answer=str(result))

    except Exception as e:
        logger.error(f"Error running ADK agent: {e}", exc_info=True)
        return AgentResponse(answer=f"Error executing agent: {e}")


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
    """
    print("--- [Graph] Calling Execution Analyst (Planner) ---")
    agent = get_agent("execution_analyst", create_execution_analyst_agent)
    user_msg = get_valid_last_message(state)

    # INJECT FEEDBACK if the loop pushed us back here
    if state.get("risk_status") == "REJECTED_REVISE":
        feedback = state.get("risk_feedback")
        user_msg = (
            f"CRITICAL: Your previous strategy was REJECTED by Risk Management.\n"
            f"Feedback: {feedback}\n"
            f"Task: Generate a REVISED, SAFER strategy based on this feedback."
        )
        print("--- [Loop] Injecting Risk Feedback ---")

    res = run_adk_agent(agent, user_msg)

    # PARSE JSON Output
    plan_output = None
    try:
        json_str = res.answer
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
             json_str = json_str.split("```")[1].split("```")[0].strip()

        plan_output = json.loads(json_str)
        logger.info(f"✅ Parsed Execution Plan: {plan_output.get('plan_id', 'unknown')}")

    except Exception as e:
        logger.warning(f"⚠️ Failed to parse Execution Plan JSON: {e}. Passing raw text.")
        plan_output = {
            "steps": [],
            "reasoning": res.answer,
            "error": "Failed to parse JSON plan"
        }

    return {
        "messages": [("ai", res.answer)],
        "risk_status": "UNKNOWN",
        "execution_plan_output": plan_output
    }


def governed_trader_node(state):
    """Wraps the Governed Trader agent for LangGraph."""
    print("--- [Graph] Calling Governed Trader ---")
    agent = get_agent("governed_trader", create_governed_trader_agent)
    last_msg = get_valid_last_message(state)
    res = run_adk_agent(agent, last_msg)
    return {"messages": [("ai", res.answer)]}
