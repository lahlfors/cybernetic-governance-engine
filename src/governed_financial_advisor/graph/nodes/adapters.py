"""
ADK Agent Adapters for LangGraph Nodes (Lite Version)

Refactored to remove strict dependency on `google-adk` for initial deployment stability.
Mocks the ADK Runner/Session logic for now.
"""

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any, List, Optional
import dataclasses

# Mock Types replacing google.genai.types for now
@dataclasses.dataclass
class Part:
    text: Optional[str] = None
    function_call: Optional[Any] = None

@dataclasses.dataclass
class Content:
    role: str
    parts: List[Part]

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

def run_adk_agent(agent_instance, user_msg: str, session_id: str = "default", user_id: str = "default_user"):
    """
    Simulates ADK Agent Runner.
    This bypasses the actual ADK Runner/Session mechanism to avoid `google-adk` dependency issues during deployment.
    It directly invokes the agent's underlying model or chain if possible, or just mocks a response if the agent is complex.
    
    CRITICAL: For this phase, we assume the specific agents (Data Analyst, etc.) might just be LangChain objects 
    or similar that we can `.invoke` or `.run`.
    """
    
    # 1. Try standard LangChain invoke/run
    try:
        if hasattr(agent_instance, "invoke"):
            # LangChain Runnable
            res = agent_instance.invoke(user_msg)
            # Handle potential OutputParser types
            if hasattr(res, "content"): return AgentResponse(answer=res.content)
            if isinstance(res, str): return AgentResponse(answer=res)
            return AgentResponse(answer=str(res))
            
        if hasattr(agent_instance, "run"):
             # Legacy LangChain
             res = agent_instance.run(user_msg)
             return AgentResponse(answer=str(res))

        # 2. If it's a raw GenAI model (Vertex)
        if hasattr(agent_instance, "generate_content"):
             res = agent_instance.generate_content(user_msg)
             text = res.text if hasattr(res, "text") else str(res)
             return AgentResponse(answer=text)
             
    except Exception as e:
        logger.error(f"Error invoking agent directly: {e}")
        return AgentResponse(answer=f"Error running agent: {e}")

    return AgentResponse(answer="[Mock] Agent execution not fully implemented without ADK.")


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
    agent = get_agent("governed_trader", create_governed_trader_agent)
    last_msg = get_valid_last_message(state)
    res = run_adk_agent(agent, last_msg)
    return {"messages": [("ai", res.answer)]}
