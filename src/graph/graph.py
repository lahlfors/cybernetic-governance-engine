from langgraph.graph import StateGraph, END
from .state import AgentState
from .nodes.supervisor_node import supervisor_node
from .nodes.adapters import (
    data_analyst_node,
    risk_analyst_node,
    execution_analyst_node,
    governed_trader_node
)
from .checkpointer import get_checkpointer

def create_graph(redis_url="redis://localhost:6379"):
    workflow = StateGraph(AgentState)

    # 1. Add Supervisor
    workflow.add_node("supervisor", supervisor_node)

    # 2. Add Adapters (Wrapping Existing Agents)
    workflow.add_node("data_analyst", data_analyst_node)
    # Risk Analyst is removed from hot path (runs offline)
    workflow.add_node("execution_analyst", execution_analyst_node)
    workflow.add_node("governed_trader", governed_trader_node)
    workflow.add_node("human_review", lambda x: x)

    # 3. Entry
    workflow.set_entry_point("supervisor")

    # 4. Supervisor Routing
    workflow.add_conditional_edges("supervisor", lambda x: x["next_step"], {
        "data_analyst": "data_analyst",
        "risk_analyst": "execution_analyst", # Legacy routing fallback -> Planner
        "execution_analyst": "execution_analyst", # Routes to Planner first
        "governed_trader": "governed_trader",
        "human_review": "human_review",
        "FINISH": END
    })

    # 5. The Strategy -> Execution Loop (Risk is Offline / NeMo Enforced)
    # Execution Analyst (Planner) goes directly to Trader (Guardrails intercept if unsafe)
    workflow.add_edge("execution_analyst", "governed_trader")

    # 6. Return to Supervisor
    workflow.add_edge("data_analyst", "supervisor")
    workflow.add_edge("governed_trader", "supervisor")
    workflow.add_edge("human_review", "supervisor")

    return workflow.compile(
        checkpointer=get_checkpointer(redis_url),
        interrupt_before=["human_review"]
    )
