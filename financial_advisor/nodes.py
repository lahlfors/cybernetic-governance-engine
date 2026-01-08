from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from financial_advisor.state import AgentState
from financial_advisor.config import Config
from financial_advisor.tools.google_search import google_search_tool
from financial_advisor.governance import opa_client
from financial_advisor.tools.trades import execute_trade, TradeOrder

# Initialize Models (Only used where specific config not applied in node)
# But strictly we should use Config in nodes.

# --- NODE 1: MARKET ANALYSIS ---
def market_analysis_node(state: AgentState):
    """
    Deterministic Flow:
    1. Receive Query (State)
    2. Execute Search Tool (Code - 100% Deterministic)
    3. Synthesize Answer (LLM)
    """
    user_query = state["messages"][-1].content

    # --- STEP 1: DETERMINISTIC TOOL EXECUTION ---
    # We do not ask the LLM. We execute the tool directly.
    # This eliminates "hallucinated tool calls" completely.
    try:
        # invoke() runs the actual Google Search Python function
        raw_results = google_search_tool.invoke(user_query)
        search_context = f"Market Data Found:\n{raw_results}"
    except Exception as e:
        search_context = f"Error retrieving market data: {str(e)}"

    # --- STEP 2: SYNTHESIS ---
    # The LLM is now purely a reasoning engine, not a controller.
    llm = ChatGoogleGenerativeAI(**Config.get_llm_config("reasoning"))

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a Senior Market Analyst. Use the provided REAL-TIME DATA to answer the user request. Do not use outside knowledge if it conflicts with the data."),
        ("human", "User Query: {query}\n\n{context}")
    ])

    chain = prompt | llm

    response = chain.invoke({
        "query": user_query,
        "context": search_context
    })

    return {"messages": [response], "market_data": response.content}

# --- NODE 2: TRADING STRATEGIES ---
def trading_strategy_node(state: AgentState):
    """Stage 2: Get strategy recommendations."""
    llm = ChatGoogleGenerativeAI(**Config.get_llm_config("reasoning"))
    data = state.get("market_data")
    prompt = f"Role: Trading Strategist. Based on this market data, propose a trading strategy. Be specific about action (buy/sell), symbol, and amount logic:\n{data}"
    response = llm.invoke(prompt)

    return {
        "messages": [response],
        "trading_strategy": response.content
    }

# --- NODE 3: RISK ASSESSMENT ---
def risk_assessment_node(state: AgentState):
    """Stage 3: Evaluate portfolio risk."""
    llm = ChatGoogleGenerativeAI(**Config.get_llm_config("reasoning"))
    strategy = state.get("trading_strategy")
    prompt = f"Role: Risk Guardian. Critically evaluate this strategy for downsides. If the strategy is high risk, state that clearly:\n{strategy}"
    response = llm.invoke(prompt)

    return {
        "messages": [response],
        "risk_assessment": response.content
    }

# --- NODE 4: GOVERNED TRADING ---
def governed_trading_node(state: AgentState):
    """Stage 4: Execute trades with policy enforcement."""
    # We use LLM only for extraction if needed, or simple logic.
    strategy = state.get("trading_strategy")
    risk = state.get("risk_assessment")

    # --- DETERMINISTIC GOVERNANCE (OPA) ---
    policy_input = {
        "action": "execute_trade",
        "strategy_description": strategy,
        "risk_assessment": risk,
        "trader_role": "senior"
    }

    # Check Policy
    if not opa_client.check_policy(policy_input):
        return {
            "messages": [("ai", "⛔ BLOCK: The proposed trade violates OPA Safety Policy.")]
        }

    # Extract info (simulated) and Execute
    if "AAPL" in str(strategy):
        try:
            # Simulated extraction
            order = TradeOrder(symbol="AAPL", amount=10, currency="USD", trader_role="senior")
            result = execute_trade(order)
            return {
                "messages": [("ai", f"✅ Trade Executed: {result}")]
            }
        except Exception as e:
             return {"messages": [("ai", f"Execution Error: {e}")]}

    return {
        "messages": [("ai", "✅ Trade Approved and Executed Successfully under Governance protocols (Simulated execution).")]
    }
