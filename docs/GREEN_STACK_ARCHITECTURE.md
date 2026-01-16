# Green Stack Governance Architecture

This repository implements the **Green Stack** governance architecture, a rigorous systems-theoretic approach to safe Agentic AI. It aligns with **ISO 42001** and **MIT STAMP/STPA** principles to ensure high-stakes agents operate within safe bounds.

## Core Philosophy: The Neuro-Symbolic Cybernetic Loop

The architecture splits the agent's cognition (Neural/Probabilistic) from its control structure (Symbolic/Deterministic).

### The 4-Layer "End-to-End" Flow

| Phase | Component | Role | Speed | Logic |
| :--- | :--- | :--- | :--- | :--- |
| **1. Define / Discovery** | **Risk Agent (A2)** | **Offline Analyst.** Hypothesizes vulnerabilities (UCAs) based on market context. | Slow (LLM) | Probabilistic |
| **2. Verify** | **Evaluator Agent** | **The Proctor.** Simulates attacks (Red Teaming) and audits traces against the STPA Ontology. | Async | Neuro-Symbolic |
| **3. Code / Bridge** | **Policy Transpiler** | **The Bridge.** Converts structured UCAs into immutable Python/Colang logic. | Pipeline | Deterministic |
| **4. Enforce** | **NeMo Guardrails** | **Runtime Guardian.** Intercepts tool calls in milliseconds to block unsafe actions. | **Real-Time** | Deterministic (Python) |

## Architectural Decisions

### 1. Offline Discovery vs. Real-Time Enforcement
**Decision:** The Risk Agent is removed from the synchronous "Hot Path" of the trade execution.
**Reasoning:** Safety Constraint 2 (SC-2) mandates that the decision loop must not exceed 200ms for high-frequency trading. LLM-based risk assessment takes seconds. Therefore, risk analysis happens *asynchronously* (Phase 1), producing rules that are enforced *instantly* (Phase 4).

### 2. The "Source of Truth" Ontology
**Location:** `src/evaluator_agent/ontology.py`
We map **STPA Unsafe Control Actions (UCAs)** as the single source of truth.
*   **UCA-1:** Authorization (Missing Token)
*   **UCA-2:** Wrong Timing (Latency > 200ms)
*   **UCA-3:** Unsafe Action (PII Leak)
*   **UCA-4:** Stopped Too Soon (Atomic Execution Failure)
*   **UCA-5:** Financial Exposure (> Limit)
*   **UCA-6:** Liquidity/Slippage (> 1% Volume)

### 3. Automated Rule Derivation
**Location:** `src/governance/transpiler.py`
We do not manually write every rule. The **Transpiler** ingests the Risk Agent's findings (e.g., "High Volatility detected, limit slippage to 0.5%") and generates the `nemo_actions.py` code automatically.

## Implementation Details

### Runtime Enforcement (Layer 3)
*   **NeMo Guardrails:** Wraps the `Governed Trader`.
*   **Actions:** `src/governance/nemo_actions.py` contains the python logic.
*   **State Awareness:** Checks `audit_trail` to ensure multi-leg trades are atomic.
*   **Temporal Logic:** Checks `time.time()` deltas to prevent trading on stale data.
*   **Authorization:** Checks cryptographic signatures (mocked AP2) to prevent replay attacks.

### Verification (Layer 4)
*   **Evaluator Auditor:** `src/evaluator_agent/auditor.py`. Grades traces 0-100 based on STPA compliance.
*   **AgentBeats Simulator:** `src/evaluator_agent/simulator.py`. Orchestrates Red Team attacks (e.g., Prompt Injection) to stress-test the rails.

## Automation
The entire loop is orchestrated by a **Vertex AI Pipeline** (`src/pipelines/green_stack_pipeline.py`), enabling Continuous Governance.
