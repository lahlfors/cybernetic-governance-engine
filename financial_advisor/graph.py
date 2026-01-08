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

# 3. Add Nodes (The 4 Execution Steps)
workflow.add_node("market_analysis", market_analysis_node)
workflow.add_node("trading_strategy", trading_strategy_node)
workflow.add_node("risk_assessment", risk_assessment_node)
workflow.add_node("governed_trading", governed_trading_node)

# 4. Define Edges (The Strict Execution Path)
# Entry -> Analysis -> Strategy -> Risk -> Trading -> End
workflow.set_entry_point("market_analysis")

workflow.add_edge("market_analysis", "trading_strategy")
workflow.add_edge("trading_strategy", "risk_assessment")
workflow.add_edge("risk_assessment", "governed_trading")
workflow.add_edge("governed_trading", END)

# 5. Compile
app = workflow.compile(checkpointer=checkpointer)
