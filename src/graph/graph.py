from langgraph.graph import END, StateGraph

from .checkpointer import get_checkpointer
from .nodes.adapters import (
    data_analyst_node,
    execution_analyst_node,
    governed_trader_node,
)
from .nodes.optimistic_nodes import (
    optimistic_execution_node,
    route_optimistic_execution,
)
from .nodes.supervisor_node import supervisor_node
from .nodes.system_2_nodes import system_2_simulation_node
from .state import AgentState


def create_graph(redis_url="redis://localhost:6379"):
    workflow = StateGraph(AgentState)

    # 1. Add Supervisor
    workflow.add_node("supervisor", supervisor_node)

    # 2. Add Adapters (Wrapping Existing Agents)
    workflow.add_node("data_analyst", data_analyst_node)
    # Risk Analyst is removed from hot path (runs offline)
    workflow.add_node("execution_analyst", execution_analyst_node)

    # 2b. Add Optimistic Execution Node (Parallel Safety + Prep)
    workflow.add_node("optimistic_execution", optimistic_execution_node)

    # 2c. Add System 2 Node (Rational Fallback)
    workflow.add_node("system_2_simulation", system_2_simulation_node)

    workflow.add_node("governed_trader", governed_trader_node)
    workflow.add_node("human_review", lambda x: x)

    # 3. Entry
    workflow.set_entry_point("supervisor")

    # 4. Supervisor Routing
    workflow.add_conditional_edges("supervisor", lambda x: x["next_step"], {
        "data_analyst": "data_analyst",
        "risk_analyst": "execution_analyst", # Legacy routing fallback -> Planner
        "execution_analyst": "execution_analyst", # Routes to Planner first
        "governed_trader": "optimistic_execution", # Force routing through Safety/Optimistic
        "human_review": "human_review",
        "FINISH": END
    })

    # 5. The Strategy -> Safety -> Execution Loop
    # Execution Analyst (Planner) -> Optimistic Execution
    workflow.add_edge("execution_analyst", "optimistic_execution")

    # Optimistic Execution -> Conditional (Trader OR Back to Planner OR System 2)
    workflow.add_conditional_edges("optimistic_execution", route_optimistic_execution, {
        "governed_trader": "governed_trader",
        "execution_analyst": "execution_analyst", # Rejected, try again
        "system_2_simulation": "system_2_simulation" # UNCERTAIN -> Causal Check
    })

    # 6. Return to Supervisor
    workflow.add_edge("data_analyst", "supervisor")
    workflow.add_edge("governed_trader", "supervisor")
    workflow.add_edge("human_review", "supervisor")
    workflow.add_edge("system_2_simulation", "supervisor") # System 2 reports back to root

    return workflow.compile(
        checkpointer=get_checkpointer(redis_url),
        interrupt_before=["human_review"]
    )
