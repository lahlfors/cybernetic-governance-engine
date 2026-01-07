# Gap Analysis: Current State vs. 2026 Green Agent Roadmap

## Executive Summary
This document analyzes the gap between the current "Cybernetic Governance" implementation (v1.0) and the "Green Agent" architecture (v2.0, 2026-2027 Roadmap). While the current system successfully implements "Defense in Depth" using OPA and Pydantic, it lacks the semantic depth (Neuro-Symbolic), hierarchical planning (HDMDP), and adaptive capabilities (AutoPT) required for the target state.

## 1. Governance Architecture

| Feature | Current State (v1.0) | Target State (Green Agent v2.0) | Gap |
| :--- | :--- | :--- | :--- |
| **Policy Engine** | **OPA (Rego)**: Deterministic, attribute-based logic. Good for "Attribute Governance" (Role X cannot do Y). | **Neuro-Symbolic (DomiKnowS)**: Logic + Neural. Capable of "Reasoning Governance" (Action X implies Y, which violates Z). | **High**: Current policy is static and rule-based, not reasoning-based. |
| **Logic Representation** | **Flat Policies**: Simple Allow/Deny based on input fields. | **Knowledge Graph**: Deep understanding of entities and relations. | **High**: No graph awareness in current OPA policies. |
| **Verification** | **Static Analysis**: Input validation (Pydantic) + Policy Check. | **Post-Training Verifiability**: Audit trails of *reasoning*, not just inputs. | **Medium**: Current telemetry tracks steps but doesn't verify the *validity* of the reasoning chain itself. |

## 2. Planning & Control

| Feature | Current State (v1.0) | Target State (Green Agent v2.0) | Gap |
| :--- | :--- | :--- | :--- |
| **Planning Paradigm** | **Flat Tool Use**: LLM picks tools from a list. Determinism enforced by `router.py`. | **HDMDP (Hierarchical)**: Explicit separation of Macro-States (Strategy) and Primitive Actions (API calls). | **Medium**: `router.py` implements a primitive form of this, but it's hardcoded, not a generalizable planner. |
| **State Management** | **Context Window**: Relying on LLM context. | **Mamba (State Space)**: Linear-time memory for infinite context. | **High**: No current implementation of State Space Models. |
| **Safety Control** | **Reactive CBFs**: Checks state *during* execution (e.g., checks cash balance before trade). | **System 2 Simulation**: Simulates outcome *before* execution (Project -> Verify -> Act). | **High**: Current system checks inputs, not projected futures. |

## 3. Adaptive Governance (Self-Healing)

| Feature | Current State (v1.0) | Target State (Green Agent v2.0) | Gap |
| :--- | :--- | :--- | :--- |
| **Policy Updates** | **Manual**: Engineers edit Rego files. | **AutoPT (Adaptive)**: Red Team attacks, Blue Team automatically updates/suggests policy changes. | **Critical**: No feedback loop exists today. |
| **Adversarial Defense** | **Static Guardrails**: NeMo Guardrails (Input/Output rails). | **Active Red Teaming**: Continuous fuzzing and jailbreak testing. | **High**: Defense is passive, not active. |

## 4. Recommendations for "Future-Ready" Refactoring

To bridge this gap without waiting for 2026 technology stacks, we recommend an **Interface-First Refactoring**:

1.  **The Constitution (Abstraction Layer)**:
    *   Wrap OPA in a `SymbolicReasoner` interface.
    *   This allows us to keep using OPA today but swap it for a Neuro-Symbolic solver (like DomiKnowS) later without rewriting the agent.

2.  **The Green Agent Service (Architectural Elevation)**:
    *   Elevate `verifier.py` from a script to a `GreenAgent` service.
    *   Implement "System 2" simulation logic (Project -> Verify) even if the simulation is simple (arithmetic) today.

3.  **Hierarchical Planner (Interface)**:
    *   Formalize the `worker_agent`'s workflow into a `HierarchicalPlanner` interface.
    *   Define `MacroState` (e.g., `RiskAssessment`) vs `PrimitiveAction` (e.g., `execute_trade`) explicitly in code.

4.  **AutoPT Loop (Skeleton)**:
    *   Implement the *structure* of the Red/Blue team loop.
    *   Even if the Red Team just uses a list of strings and the Blue Team just logs errors, the *feedback architecture* will be in place.
