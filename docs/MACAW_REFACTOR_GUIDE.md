# MACAW Refactoring Guide: Transition to Neuro-Cybernetic Governance (Optimistic Parallel)

## 1. Executive Summary

This document details the architectural transformation of the **Governed Financial Advisor** into a **Neuro-Cybernetic Governance** system.

The architecture has shifted from a "Sequential Blocking" model to an **"Optimistic Parallel Execution"** model. This design prioritizes speed and reactivity, allowing the **Executor (System 1)** to act immediately while the **Evaluator (System 3)** monitors in real-time, intervening only if safety constraints are violated.

This aligns with **ISO/IEC 42001 (AIMS)** and **SR 11-7 (Model Risk Management)** by embedding safety controls directly into the execution fabric via a "Digital Immune System".

---

## 2. Architectural Shift

### Before: Sequential Blocking (The "Safety Tax")
*   **Flow:** `Planner -> Evaluator -> Executor`
*   **Philosophy:** "Pessimistic Execution" - Assume failure, block until proven safe.
*   **Drawback:** High latency due to waiting for full safety checks before any action.

### After: Optimistic Parallel Execution (The "Digital Immune System")
*   **Flow:** `Planner -> [Evaluator || Executor] -> Explainer`
*   **Philosophy:** "Optimistic Execution with Interrupts" - Act fast, check concurrently, interrupt on violation.
*   **Key Mechanism:** A shared state flag (`safety_violation` in Redis) allows the Evaluator to halt the Executor mid-flight.

---

## 3. Core Components

### 3.1. The Planner (System 4 Feedforward)
*   **Component:** `src/governed_financial_advisor/agents/execution_analyst/agent.py`
*   **Role:** Generates the execution plan.
*   **Logic:** Spawns both the **Executor** and **Evaluator** branches simultaneously upon plan creation.

### 3.2. The Executor (System 1 Implementation)
*   **Component:** `src/governed_financial_advisor/agents/governed_trader/agent.py`
*   **Role:** Executes the trade immediately.
*   **Constraint:** Polls the `safety_violation` flag in `src/gateway/core/tools.py` before finalizing any external API call (HTTP POST). If the flag is set, it aborts.

### 3.3. The Evaluator (System 3 Real-Time Monitor)
*   **Component:** `src/governed_financial_advisor/agents/evaluator/agent.py`
*   **Role:** Races against the Executor to verify safety constraints (STPA, OPA, CBF).
*   **Action:** If a violation is detected, it triggers the `trigger_safety_intervention` tool, which sets the `safety_violation` flag, stopping the Executor.

### 3.4. The Gateway (Infrastructure Enforcement)
*   **Component:** `src/gateway/server/hybrid_server.py`
*   **Role:** Central enforcement point (HTTP/MCP).
*   **Tools:**
    *   `execute_trade`: Checks Redis for interrupts.
    *   `check_safety_constraints`: Used by Evaluator for dry-run validation.
    *   `trigger_safety_intervention`: Used by Evaluator to signal a stop.
*   **Logic:** Integrates `STPAValidator` (in `src/gateway/governance/stpa_validator.py`) to enforce deterministic safety rules (e.g., latency limits, authorization).

---

## 4. Safety Mechanisms (Modules 1, 5, 6, 7)

1.  **STPA Constraints (Module 5):** Defined in `src/gateway/governance/ontology.py` and enforced by `STPAValidator`. Blocks "Unsafe Control Actions" (UCAs).
2.  **Interrupt Mechanism (Module 6):** Redis-based shared state allows asynchronous interruption of running processes.
3.  **Red Teaming (Module 1):** `tests/red_teaming/test_adversarial.py` validates resilience against adversarial attacks.
4.  **Control Barrier Functions (Module 7):** Enforced by `SymbolicGovernor` in Gateway to prevent boundary violations (e.g., bankruptcy).

---

## 5. Deployment

*   **Infrastructure:** GKE Standard (for vLLM GPU persistence).
*   **State:** Redis (for shared safety flags).
*   **Observability:** OpenTelemetry (OTel) traces the "race" between Executor and Evaluator.
