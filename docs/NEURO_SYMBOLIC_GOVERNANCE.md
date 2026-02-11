# Neuro-Symbolic Governance Architecture

## Overview

The **Neuro-Symbolic Governance** layer implements the "Cybernetic" control system for the Financial Advisor. It combines probabilistic AI (Neural) with deterministic logic (Symbolic) to ensure safety and compliance.

This architecture specifically addresses **Module 5 (Systemic Accident Prevention)** and **Module 7 (Deterministic Safety Guarantees)** of the Capstone Project.

---

## Architecture Components

### 1. Symbolic Governor (`src/gateway/governance/symbolic_governor.py`)
The central enforcement engine residing in the Gateway. It wraps every tool execution request.

*   **Responsibility:** Intercepts tool calls and validates them against safety rules *before* execution (or concurrently in Optimistic mode).
*   **Checks:**
    1.  **STPA Validation:** Checks for Unsafe Control Actions (UCAs) defined in the ontology.
    2.  **SR 11-7 Confidence:** Enforces minimum confidence scores (e.g., 0.95).
    3.  **CBF Safety:** Checks Control Barrier Functions (e.g., drawdown limits).
    4.  **OPA Policy:** Checks regulatory policies (e.g., restricted regions).

### 2. STPA Validator (`src/gateway/governance/stpa_validator.py`)
Implements the System-Theoretic Process Analysis (STPA) logic.

*   **Ontology:** Uses `src/gateway/governance/ontology.py` to define:
    *   **UCAs (Unsafe Control Actions):** Specific hazards (e.g., "Trade with >200ms latency", "Write DB without Auth").
    *   **Constraints:** Logic to detect these hazards in tool parameters.
*   **Logic:** Deterministic rule engine. If a parameter violates a constraint, it returns a violation.

### 3. Redis-Based Interrupt Mechanism (The "Digital Immune System")
Enables the **Optimistic Parallel Execution** model.

*   **Concept:** The Executor runs trades immediately, assuming safety. The Evaluator runs checks in parallel.
*   **Mechanism:**
    *   **Shared Flag:** `safety_violation` key in Redis.
    *   **Trigger:** The Evaluator calls `trigger_safety_intervention(reason)` tool in Gateway.
    *   **Enforcement:** The `execute_trade` tool polls Redis. If `safety_violation` is set, it aborts execution (throws `RuntimeError`).
*   **Latency:** This allows the system to react in milliseconds to safety threats even during execution.

---

## Workflow

1.  **Plan:** Agent generates a plan.
2.  **Fork:** Graph spawns **Executor** and **Evaluator** branches.
3.  **Executor:** Starts `execute_trade`. Checks Redis. Prepares HTTP request.
4.  **Evaluator:** Calls `check_safety_constraints` (Dry Run of Governor).
5.  **Race:**
    *   *Scenario A (Safe):* Evaluator approves. Executor completes HTTP request. Both join at Explainer.
    *   *Scenario B (Unsafe):* Evaluator detects violation -> Calls `trigger_safety_intervention`.
    *   *Interrupt:* Executor checks Redis right before HTTP call -> Sees flag -> Aborts.
6.  **Log:** Trace logged to OTel.

---

## Compliance Mapping

*   **SR 11-7:** Symbolic checks ensure "conceptual soundness" and block hallucinations.
*   **ISO 42001:** "Plan-Do-Check-Act" is implemented via the parallel Evaluator loop.
*   **NIST AI RMF:** Safety/Security managed by the Governor.
