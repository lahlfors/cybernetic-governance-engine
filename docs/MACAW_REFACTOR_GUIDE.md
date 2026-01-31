# MACAW Refactoring Guide: Transition to Agentic Governance

## 1. Executive Summary

This document details the architectural refactoring of the **Governed Financial Advisor** from a parallel, optimistic execution model to the **Capital One MACAW (Multi-Agent Conversational AI Workflow)** pattern.

The refactor prioritizes **Safety and Correctness** over raw latency for high-risk financial operations. It introduces a strict **Cybernetic Governance** model aligned with **ISO/IEC 42001**, utilizing the **Viable System Model (VSM)** to define agent roles.

---

## 2. Architectural Shift

### Before: Optimistic Parallelism
*   **Flow:** `Supervisor -> [Trader Prep || Safety Check] -> Trader`
*   **Philosophy:** "Optimistic Execution" - Assume success, check safety in parallel to save time.
*   **Risk:** "Safety Tax" is hidden but failures are messy. Complex "Worker/Verifier" logic buried inside the Trader agent.

### After: MACAW Sequential Blocking
*   **Flow:** `Supervisor -> Planner -> Evaluator -> Executor -> Explainer`
*   **Philosophy:** "Optimistic Planning, Pessimistic Execution" - Plan fast, but **BLOCK** execution until a Simulation/Evaluation phase is passed.
*   **Benefit:** Strict Separation of Concerns, Feedforward Control (Simulation), and Second-Order Cybernetics (Watcher/Evaluator).

---

## 3. Component Refactors

### 3.1. The Planner (System 4 Feedforward)
*   **Component:** `src/governed_financial_advisor/agents/execution_analyst/agent.py`
*   **Change:**
    *   Renamed role to **Planner**.
    *   Prompt updated to generate `ExecutionPlan` (DAG of steps) based on user intent and strategy.
    *   **Goal:** Anticipate future states (Feedforward).

### 3.2. The Evaluator (System 3 Control)
*   **Component:** `src/governed_financial_advisor/agents/evaluator/agent.py` (**NEW**)
*   **Change:**
    *   Created a dedicated **Evaluator Agent**.
    *   **Simulation Loop:** Runs `check_market_status`, `verify_policy_opa`, `verify_consensus`, and `verify_semantic_nemo`.
    *   **Optimization:** The `Evaluator Node` runs these tools in **Parallel** (`asyncio.gather`) internally to minimize latency, but **Blocks** the graph flow until all pass.
    *   **Real-World Wiring:** Mocks have been replaced with real integrations. `verify_policy_opa` calls the `OPAClient` (Gateway Stub), and `verify_consensus` invokes the Multi-Agent Debate engine.
    *   **Output:** `EvaluationResult` (Verdict + Reasoning).

### 3.3. The Executor (System 1 Implementation)
*   **Component:** `src/governed_financial_advisor/agents/governed_trader/agent.py`
*   **Change:**
    *   Stripped of all "Reasoning" and "Strategy" logic.
    *   Refactored into a "Dumb Executor" (System 1).
    *   **Strict Constraint:** Can ONLY execute the `execute_trade` tool as specified in the approved `ExecutionPlan`.

### 3.4. The Explainer (System 3 Monitoring)
*   **Component:** `src/governed_financial_advisor/agents/explainer/agent.py` (**NEW**)
*   **Change:**
    *   Created a dedicated **Explainer Agent**.
    *   **Faithfulness:** Compares `execution_result` (Technical) with `execution_plan_output` (Intent) to ensure the user report is accurate.
    *   Prevents "Post-Hoc Rationalization".

---

## 4. Deletions & Clean-Up

*   **Deleted:** `src/governed_financial_advisor/graph/nodes/optimistic_nodes.py`
    *   **Reason:** The "Optimistic Execution Node" logic (Parallel Prep + Safety) was incompatible with the strict MACAW "Simulation" step.
*   **Removed:** `SequentialAgent` logic in `GovernedTrader`.
    *   **Reason:** Redundant. The Graph itself now manages the sequential flow (`Planner -> Evaluator -> Executor`).

---

## 5. Documentation Updates

The following documentation has been updated to reflect this refactor:

1.  **`ARCHITECTURE.md`**:
    *   Added **MACAW Architecture** diagram.
    *   Mapped components to **Viable System Model (VSM)**.
    *   Detailed the **"Optimistic Planning, Pessimistic Execution"** latency strategy.
    *   Added **vLLM Integration** details (Hybrid Inference).

2.  **`FUNCTIONAL_SPEC.md`**:
    *   Updated "Component Wiring" to show the sequential flow.
    *   Documented the new **Evaluator** and **Explainer** roles.

3.  **`docs/SYSTEM_DESCRIPTION_ISO_42001.md`**:
    *   Incorporated the **Cybernetic Analysis** (Feedforward, Requisite Variety).
    *   Mapped ISO 42001 clauses (6.1, 9.1) to the new Agentic components.
