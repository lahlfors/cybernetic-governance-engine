import logging
from langchain_core.runnables.config import RunnableConfig
from src.agents.root_agent import root_agent
from src.agents.data_analyst.agent import data_analyst_agent
from src.agents.risk_analyst.agent import risk_analyst_agent
from src.agents.execution_analyst.agent import execution_analyst_agent
from src.agents.governed_trader.agent import governed_trading_agent

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

logger = logging.getLogger(__name__)

# Session management for the ADK agents
session_service = InMemorySessionService()

def run_adk_agent(agent_instance, user_msg: str, session_id: str = "default"):
    """Wraps the ADK Agent Runner to execute a turn and return the result object."""
    runner = Runner(agent=agent_instance, session_service=session_service, app_name="financial_advisor")
    # Return the full result object so we can inspect function calls (intent)
    return runner.run(session_id=session_id, query=user_msg)

# --- Node Implementations ---

def get_session_id(config: RunnableConfig) -> str:
    return config.get("configurable", {}).get("thread_id", "default")

def data_analyst_node(state, config: RunnableConfig):
    print("--- [Graph] Calling Data Analyst ---")
    last_msg = state["messages"][-1].content
    session_id = get_session_id(config)
    res = run_adk_agent(data_analyst_agent, last_msg, session_id=session_id)
    return {"messages": [("ai", f"Data Analysis: {res.answer}")]}

def risk_analyst_node(state, config: RunnableConfig):
    print("--- [Graph] Calling Risk Analyst ---")
    last_plan = state["messages"][-1].content
    session_id = get_session_id(config)
    res = run_adk_agent(risk_analyst_agent, f"Evaluate this plan: {last_plan}", session_id=session_id)

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

def execution_analyst_node(state, config: RunnableConfig):
    print("--- [Graph] Calling Execution Analyst (Planner) ---")
    user_msg = state["messages"][-1].content
    session_id = get_session_id(config)

    # INJECT FEEDBACK if the loop pushed us back here
    if state.get("risk_status") == "REJECTED_REVISE":
        feedback = state.get("risk_feedback")
        user_msg = (
            f"CRITICAL: Your previous strategy was REJECTED by Risk Management.\n"
            f"Feedback: {feedback}\n"
            f"Task: Generate a REVISED, SAFER strategy based on this feedback."
        )
        print(f"--- [Loop] Injecting Risk Feedback ---")

    res = run_adk_agent(execution_analyst_agent, user_msg, session_id=session_id)

    # Reset status so we can potentially loop again or proceed
    return {"messages": [("ai", res.answer)], "risk_status": "UNKNOWN"}

def governed_trader_node(state, config: RunnableConfig):
    print("--- [Graph] Calling Governed Trader ---")
    last_msg = state["messages"][-1].content
    session_id = get_session_id(config)
    res = run_adk_agent(governed_trading_agent, last_msg, session_id=session_id)
    return {"messages": [("ai", res.answer)]}
