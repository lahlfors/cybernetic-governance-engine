from langgraph.graph import StateGraph, END
from langgraph.checkpoint.redis import RedisSaver
from redis import Redis
import os

from financial_advisor.state import AgentState
from financial_advisor.nodes import (
    market_analysis_node,
    trading_strategy_node,
    risk_assessment_node,
    governed_trading_node
)

# 1. Persistence (Redis)
redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
redis_client = Redis.from_url(redis_url)
checkpointer = RedisSaver(conn=redis_client)

# 2. Define Graph
workflow = StateGraph(AgentState)

# 3. Add Nodes
workflow.add_node("market_analysis", market_analysis_node)
workflow.add_node("trading_strategy", trading_strategy_node)
workflow.add_node("risk_assessment", risk_assessment_node)
workflow.add_node("governed_trading", governed_trading_node)

# 4. Define Edges (The HD-MDP Logic)
workflow.set_entry_point("market_analysis")

workflow.add_edge("market_analysis", "trading_strategy")
workflow.add_edge("trading_strategy", "risk_assessment")

# Conditional Edge Logic
def should_revise(state: AgentState):
    """
    Decides whether to loop back for correction or proceed to execution.
    """
    risk_assessment = state.get("risk_assessment", "")
    feedback = state.get("feedback")
    count = state.get("revision_count", 0)

    # 1. Circuit Breaker
    MAX_RETRIES = 3
    if count > MAX_RETRIES:
        return "halt" # Stop if too many attempts

    # 2. Risk Check
    # If explicit "REJECT" status or feedback provided
    if feedback or "STATUS: REJECT" in risk_assessment:
        return "revise"

    # 3. Default
    return "proceed"

workflow.add_conditional_edges(
    "risk_assessment",
    should_revise,
    {
        "revise": "trading_strategy",
        "proceed": "governed_trading",
        "halt": END
    }
)

workflow.add_edge("governed_trading", END)

# 5. Compile
app = workflow.compile(checkpointer=checkpointer)
