from langgraph.graph import StateGraph, END
from typing import TypedDict, Dict, Any, Literal

# Mock State definition since we don't have the full AgentState file in context easily
# In real code, import AgentState
class AgentState(TypedDict):
    proposed_action: str
    context: Dict[str, Any]
    governance_result: Dict[str, Any]
    final_outcome: str

from src.governance.engine import PolicyEngine
from src.governance.system2 import system_2_simulation_node

# --- 1. The Conditional Edge Logic ---
def route_governance_result(state: AgentState) -> Literal["execute", "reject", "system_2"]:
    result = state.get("governance_result", {})
    status = result.get("status")

    if status == "ALLOW":
        return "execute"
    elif status == "DENY":
        return "reject"
    else:
        # Status is UNCERTAIN (or missing)
        print(f"OPA Uncertain: {result.get('reason')}")
        return "system_2"

# --- Nodes ---
def safety_check_node(state: AgentState):
    print("--- [Safety Check] calling OPA ---")
    engine = PolicyEngine()
    result = engine.evaluate({
        "action": state["proposed_action"],
        "context": state["context"]
    })
    return {"governance_result": result}

def execute_transaction_node(state: AgentState):
    print("--- [Execution] Transaction Processed ---")
    return {"final_outcome": "EXECUTED"}

def rejection_handler_node(state: AgentState):
    print("--- [Rejection] Transaction Blocked ---")
    return {"final_outcome": "BLOCKED"}

# --- Wiring ---
def create_hybrid_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("safety_check", safety_check_node) # Calls OPA
    workflow.add_node("system_2", system_2_simulation_node) # Runs DoWhy
    workflow.add_node("execute", execute_transaction_node)
    workflow.add_node("reject", rejection_handler_node)

    workflow.set_entry_point("safety_check")

    # The Router
    workflow.add_conditional_edges(
        "safety_check",
        route_governance_result,
        {
            "execute": "execute",
            "reject": "reject",
            "system_2": "system_2"
        }
    )

    # System 2 loops back to the routing logic?
    # Or directly to execute/reject?
    # The user example said "Loop Back" but the code showed "route_governance_result".
    # Since System 2 updates "governance_result", rerouting works.
    workflow.add_conditional_edges(
        "system_2",
        route_governance_result,
        {
            "execute": "execute",
            "reject": "reject",
            "system_2": "reject" # Avoid infinite loop if System 2 fails to resolve
        }
    )

    return workflow.compile()
