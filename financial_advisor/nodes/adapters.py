from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

# Import YOUR EXISTING AGENTS
from financial_advisor.sub_agents.data_analyst.agent import data_analyst_agent
from financial_advisor.sub_agents.risk_analyst.agent import risk_analyst_agent
from financial_advisor.sub_agents.execution_analyst.agent import execution_analyst_agent
from financial_advisor.sub_agents.governed_trader.agent import governed_trading_agent

# Initialize session service ONCE
session_service = InMemorySessionService()

def run_adk_agent(agent_instance, state, prefix="", session_id: str = "default"):
    """
    Wraps an ADK Agent in a Runner to execute a turn.
    """
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
    # Custom logic: Parse the risk agent's text output to update state flags
    res = run_adk_agent(risk_analyst_agent, state)
    text = res["messages"][0][1]

    # Simple parsing of your existing agent's output to drive the Graph Loop
    status = "APPROVED"
    if "REJECT" in text.upper() or "HIGH RISK" in text.upper():
        status = "REJECTED_REVISE"

    return {**res, "risk_status": status, "risk_feedback": text}

def execution_analyst_node(state):
    print("--- [Graph] Calling Existing Execution Analyst ---")
    return run_adk_agent(execution_analyst_agent, state)

def governed_trader_node(state):
    print("--- [Graph] Calling Existing Governed Trader ---")
    return run_adk_agent(governed_trading_agent, state)
