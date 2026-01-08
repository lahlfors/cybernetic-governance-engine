from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from opentelemetry import trace

from financial_advisor.state import AgentState
from financial_advisor.config import Config
from financial_advisor.tools.google_search import google_search_tool
from financial_advisor.governance import opa_client
from financial_advisor.tools.trades import execute_trade, TradeOrder

tracer = trace.get_tracer(__name__)

# --- NODE 1: MARKET ANALYSIS ---
@tracer.start_as_current_span("market_analysis_node")
def market_analysis_node(state: AgentState):
    """
    Deterministic Flow:
    1. Receive Query (State)
    2. Execute Search Tool (Code - 100% Deterministic)
    3. Synthesize Answer (LLM)
    """
    current_span = trace.get_current_span()
    current_span.set_attribute("iso.control_id", "8.2.1")
    current_span.set_attribute("iso.phase", "analysis")

    user_query = state["messages"][-1].content
    current_span.set_attribute("input.query_length", len(user_query))

    # --- STEP 1: DETERMINISTIC TOOL EXECUTION ---
    try:
        raw_results = google_search_tool.invoke(user_query)
        search_context = f"Market Data Found:\n{raw_results}"
        current_span.set_attribute("tool.status", "success")
    except Exception as e:
        search_context = f"Error retrieving market data: {str(e)}"
        current_span.set_attribute("tool.status", "error")
        current_span.record_exception(e)

    # --- STEP 2: SYNTHESIS ---
    llm = ChatGoogleGenerativeAI(**Config.get_llm_config("reasoning"))

    # Improved Prompt
    system_prompt = """You are a Senior Market Analyst.
Your goal is to provide a comprehensive, fact-based market analysis based STRICTLY on the provided data.

WARNINGS:
- Do NOT use outside knowledge. If the provided data is insufficient, state this clearly.
- Do NOT hallucinate stock prices or trends.
- DISCLAIMER: This analysis is for informational purposes only and does not constitute financial advice.

STRUCTURE:
- Executive Summary
- Key Market Data
- Relevant News
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "User Query: {query}\n\n{context}")
    ])

    chain = prompt | llm

    response = chain.invoke({
        "query": user_query,
        "context": search_context
    })

    return {"messages": [response], "market_data": response.content}

# --- NODE 2: TRADING STRATEGIES ---
@tracer.start_as_current_span("trading_strategy_node")
def trading_strategy_node(state: AgentState):
    """Stage 2: Get strategy recommendations."""
    current_span = trace.get_current_span()
    current_span.set_attribute("iso.control_id", "8.2.2")

    llm = ChatGoogleGenerativeAI(**Config.get_llm_config("reasoning"))
    data = state.get("market_data")

    # Improved Prompt
    system_prompt = """You are a Trading Strategist.
Based on the provided market analysis, propose a clear trading strategy.

WARNINGS:
- Your strategy must be supported by the data.
- You must specify the Action (Buy/Sell/Hold), Symbol, and reasoning.
- DISCLAIMER: This is a simulation. Not real investment advice.
"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Market Analysis:\n{data}")
    ])

    response = prompt | llm
    response = response.invoke({"data": data})

    return {
        "messages": [response],
        "trading_strategy": response.content
    }

# --- NODE 3: RISK ASSESSMENT ---
@tracer.start_as_current_span("risk_assessment_node")
def risk_assessment_node(state: AgentState):
    """Stage 3: Evaluate portfolio risk."""
    current_span = trace.get_current_span()
    current_span.set_attribute("iso.control_id", "8.2.3")

    llm = ChatGoogleGenerativeAI(**Config.get_llm_config("reasoning"))
    strategy = state.get("trading_strategy")

    # Improved Prompt
    system_prompt = """You are a Risk Guardian.
Your job is to critically evaluate the proposed trading strategy for safety and compliance.

WARNINGS:
- Identify high-risk factors (volatility, lack of data, regulatory concerns).
- If the strategy is vague or dangerous, flag it immediately.
- Safety is your top priority.
"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Proposed Strategy:\n{strategy}")
    ])

    response = prompt | llm
    response = response.invoke({"strategy": strategy})

    return {
        "messages": [response],
        "risk_assessment": response.content
    }

# --- NODE 4: GOVERNED TRADING ---
@tracer.start_as_current_span("governed_trading_node")
def governed_trading_node(state: AgentState):
    """Stage 4: Execute trades with policy enforcement."""
    current_span = trace.get_current_span()
    current_span.set_attribute("iso.control_id", "8.2.4")

    strategy = state.get("trading_strategy")
    risk = state.get("risk_assessment")

    # --- DETERMINISTIC GOVERNANCE (OPA) ---
    policy_input = {
        "action": "execute_trade",
        "strategy_description": strategy,
        "risk_assessment": risk,
        "trader_role": "senior"
    }

    current_span.set_attribute("governance.policy_check", "opa")

    # Check Policy
    if not opa_client.check_policy(policy_input):
        current_span.set_attribute("governance.result", "blocked")
        return {
            "messages": [("ai", "⛔ BLOCK: The proposed trade violates OPA Safety Policy.")]
        }

    current_span.set_attribute("governance.result", "allowed")

    # Extract info (simulated) and Execute
    if "AAPL" in str(strategy):
        try:
            # Simulated extraction
            order = TradeOrder(symbol="AAPL", amount=10, currency="USD", trader_role="senior")
            result = execute_trade(order)
            current_span.set_attribute("execution.status", "success")
            return {
                "messages": [("ai", f"✅ Trade Executed: {result}")]
            }
        except Exception as e:
             current_span.record_exception(e)
             current_span.set_attribute("execution.status", "error")
             return {"messages": [("ai", f"Execution Error: {e}")]}

    return {
        "messages": [("ai", "✅ Trade Approved and Executed Successfully under Governance protocols (Simulated execution).")]
    }
