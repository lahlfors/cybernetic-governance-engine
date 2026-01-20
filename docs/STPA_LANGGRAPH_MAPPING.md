# Mapping STPA to LangGraph: The Control Loop

This document explains how the abstract **System-Theoretic Process Analysis (STPA)** concepts are concretely mapped to the **LangGraph** execution architecture using the `ControlLoop` metadata class.

## 1. The Core Concept: Control Loop Metadata

In STPA, safety is treated as a control problem. To enforce this, we must explicitly model the "Control Loop" that is currently active. We do not assume the system is a monolith; instead, it is a hierarchy of controllers.

The `ControlLoop` class (defined in `src/governance/stpa.py`) acts as the "Name Tag" or "Context Header" for the current execution step.

```python
class ControlLoop(BaseModel):
    id: str                 # e.g., "LOOP-TRADE-001"
    name: str               # e.g., "Trade Execution Loop"
    controller: str         # e.g., "GovernedTrader" (The Agent)
    controlled_process: str # e.g., "Exchange API" (The External System)
    control_actions: List[str] # e.g., ["execute_order"] (Allowed Tools)
    feedback_mechanism: str # e.g., "Order Confirmation" (Return Values)
```

## 2. Mapping Table: STPA vs. LangGraph

| STPA Entity | LangGraph Component | Example Implementation |
| :--- | :--- | :--- |
| **Controller** | **Graph Node** | The `governed_trader` node is the active controller issuing commands. |
| **Process** | **External System** | The real-world system accessed via Tools (e.g., The Stock Market via `execute_trade`). |
| **Control Action** | **Tool Call** | When the Agent calls `execute_trade(...)`, it is issuing a Control Action. |
| **Feedback** | **Tool Output / State** | The return value of the tool (e.g., `{"status": "FILLED"}`) or updated `AgentState`. |
| **Actuator** | **Tool Definition** | The Python function wrapping the API (e.g., `src/tools/trades.py`). |
| **Sensor** | **Data Tools** | Tools that fetch state (e.g., `get_market_data`, `get_position`). |

## 3. Implementation Logic

### A. Initialization (The Supervisor)
The `supervisor_node` acts as the **System 3 Supervisor** (from VSM). It decides *which* loop to activate.

*   When routing to the **Execution Analyst**, it initializes the **"Planning Loop"**.
    *   *Controller:* Planner
    *   *Process:* The Plan
*   When routing to the **Governed Trader**, it initializes the **"Trading Loop"**.
    *   *Controller:* Trader
    *   *Process:* The Market

```python
# src/graph/nodes/supervisor_node.py
if "trade" in target:
    next_step = "governed_trader"
    stpa_metadata = ControlLoop(
        id="LOOP-TRADE-001",
        controller="GovernedTrader",
        control_actions=["execute_order"],
        ...
    )
    # Inject into State
    updated_state["control_loop_metadata"] = stpa_metadata
```

### B. Transport (The State)
The `AgentState` carries this metadata like a "Context Token". This ensures that downstream nodes know *who* is acting and *what* the constraints are.

```python
# src/graph/state.py
class AgentState(TypedDict):
    ...
    control_loop_metadata: Optional[ControlLoop]
```

### C. Enforcement (The Safety Node)
The `safety_check_node` (Layer 2 Enforcer) reads this metadata to apply context-aware policies. It injects the `stpa_context` into the OPA (Open Policy Agent) payload.

*   **Scenario:** A "Planner" trying to `execute_trade` would be BLOCKED because its `ControlLoop` defines its allowed actions as `["propose_trade"]`, not `["execute_trade"]`.
*   **Scenario:** A "Trader" trying to `execute_trade` is ALLOWED (subject to other checks like limits), because that action is valid for its Loop.

```python
# src/graph/nodes/safety_node.py
loop_metadata = state.get("control_loop_metadata")
opa_input["stpa_context"] = {
    "loop_id": loop_metadata.id,
    "controller": loop_metadata.controller,
    "allowed_actions": loop_metadata.control_actions
}
```

## 4. Why this matters?

Without this explicit mapping, the system is just "Agents calling Tools".
With this mapping, the system becomes a **Hierarchy of Control Loops**, where every action is:
1.  **Attributable** to a specific Controller.
2.  **Scoped** to a specific Process.
3.  **Constrained** by the definitions of that Loop.

This allows us to answer STPA-style questions like: *"Did the Controller receive Feedback?"* or *"Was the Control Action appropriate for the Process State?"* programmaticlly.
