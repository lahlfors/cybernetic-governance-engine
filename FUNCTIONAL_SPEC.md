# Functional Specification & Technical Architecture

## 1. Executive Summary

This document describes the implemented functionality of the **Governed Financial Advisor** as determined by static code analysis. The system uses a **Hybrid Architecture** combining **LangGraph** (for deterministic workflow orchestration) and **Google Agent Development Kit (ADK)** (for LLM reasoning), secured by a multi-layer **"Governance Sandwich"**.

## 2. System Architecture

The system is organized into a **Control Plane** (LangGraph) and a **Reasoning Plane** (Google ADK), with strict isolation.

### 2.1 Control Plane: LangGraph (`src/governed_financial_advisor/graph/`)
The workflow is a State Machine (`StateGraph`) defined in `graph.py` with the following nodes:

1.  **Supervisor Node (`supervisor_node.py`)**:
    *   Acts as the entry point.
    *   Runs the Root Agent (`financial_coordinator`) to interpret user intent.
    *   **Route Interception**: Intercepts the `route_request` tool call to deterministically decide the next step (`data_analyst`, `execution_analyst`, `risk_analyst`, `governed_trader`, or `FINISH`).
    *   Manages User Profile state (`risk_attitude`, `investment_period`).

2.  **Adapter Nodes (`nodes/adapters.py`)**:
    *   Wraps Google ADK Agents to make them compatible with LangGraph.
    *   Uses `run_adk_agent` to execute a single turn of an ADK agent using `google.adk.runners.Runner`.
    *   Parses structured output (e.g., JSON from `execution_analyst`) to update the shared `AgentState`.

3.  **Optimistic Execution Node (`nodes/optimistic_nodes.py`)**:
    *   Implements the **"Latency as Currency"** pattern.
    *   Runs three tasks in parallel:
        *   **Rail A (Safety):** OPA Policy Check via `safety_check_node`.
        *   **Rail B (Semantic):** NeMo Guardrails check via `check_nemo_guardrails`.
        *   **Rail C (Tool Prep):** `trader_prep_node` (simulates read-only pre-checks).
    *   **Logic:** If both Rails A and B pass, the result of Rail C is used. If either fails, Rail C is cancelled.

### 2.2 Reasoning Plane: Google ADK Agents (`src/governed_financial_advisor/agents/`)
Agents are instantiated as `LlmAgent` or `SequentialAgent` using Vertex AI models.

| Agent | Type | Role | Key Tools/Patterns |
|-------|------|------|--------------------|
| **Financial Coordinator** | `LlmAgent` | Root Router | `route_request`. Does not expose sub-agents directly. |
| **Governed Trader** | `SequentialAgent` | Execution | **Worker:** Generates strategies.<br>**Verifier:** Validates via `verify_with_nemo_guardrails` and `execute_trade`. |
| **Risk Analyst** | `LlmAgent` | Audit | Uses `GovernanceClient` (vLLM) to generate strict `RiskAssessment` JSON. Loads dynamic hazards via `PolicyLoader`. |
| **Execution Analyst** | `LlmAgent` | Planner | Generates `ExecutionPlan` JSON. |
| **Data Analyst** | `LlmAgent` | Research | *Standard ADK agent (inferred).* |

### 2.3 Governance Layer ("The Sandwich")
Governance is injected at multiple points to ensure safety.

1.  **Open Policy Agent (OPA) (`governance/client.py`)**:
    *   **Client:** `OPAClient` connects via HTTP or Unix Domain Socket.
    *   **Resilience:** Implements `CircuitBreaker` (Fail-Fast) and "Bankruptcy Protocol" (Hard Latency Ceiling).
    *   **Integration:** Used in `optimistic_execution_node` and via `@governed_tool` decorator.

2.  **NeMo Guardrails (`utils/nemo_manager.py`)**:
    *   **Manager:** Wraps `nemoguardrails` with a custom `GeminiLLM` provider.
    *   **Features:** Supports Vertex AI Context Caching and OTel instrumentation (`NeMoOTelCallback`).
    *   **Usage:** Validates input in `optimistic_nodes.py` and verifying trade intent in `Governed Trader`.

3.  **Mathematical Safety (`governance/safety.py`)**:
    *   **Mechanism:** Control Barrier Function (CBF) enforcing $h(next) \ge (1-\gamma)h(current)$.
    *   **Persistence:** Uses `RedisWrapper` to store state (e.g., `current_cash`).
    *   **Check:** `verify_action` method called within `@governed_tool`.

## 3. Infrastructure & Telemetry

### 3.1 LLM Routing (`infrastructure/llm_client.py`)
*   **HybridClient:** Routes traffic based on SLA and capability.
    *   **Fast Path:** vLLM (Self-hosted).
    *   **Reliable Path:** Vertex AI (Gemini).
*   **Modes:**
    *   `chat`: Streaming, monitors Time-To-First-Token (TTFT). Falls back if > `fallback_threshold_ms`.
    *   `verifier`: Blocking, optimized for throughput/determinism.
*   **Proof of Determinism:** Logs FSM constraints (`json_schema`, `regex`) to telemetry.

### 3.2 Telemetry (`utils/telemetry.py`)
*   **Stack:** OpenTelemetry + Google Cloud Trace + Langfuse.
*   **Tiered Storage:**
    *   **Hot:** Cloud Trace (Cost Optimized).
    *   **Cold:** Parquet (Archive).
    *   **Langfuse:** Detailed traces via OTLP.
*   **Smart Sampling:** 100% sampling for "RISKY" or "WRITE" spans; 1% for "READ".

### 3.3 Persistence (`infrastructure/redis_client.py`)
*   **RedisWrapper:** Tries to connect to `REDIS_HOST`. Falls back to in-memory `_local_cache` if connection fails.
*   Used by: `ControlBarrierFunction` (Safety) and `StateGraph` (Checkpointing).

---

## 4. Gap Analysis (Code vs. Documentation/Memory)

The following discrepancies were identified between the **actual codebase** and the provided **memory/documentation context**.

| Feature | Memory / Documentation Claims | Actual Code Implementation | Severity |
|---------|-------------------------------|----------------------------|----------|
| **Architecture** | "ADK Native model, removing LangGraph entirely." | **Hybrid:** LangGraph is the core orchestrator (`src/graph`). ADK is used for agents only. | 🔴 High |
| **Persistence** | "Redis has been completely removed... Persistent data is stored in Firestore." | **Redis:** `redis_client.py` is actively used by `safety.py` and `graph.py`. No Firestore code found in analyzed paths. | 🔴 High |
| **Safety Storage** | "ControlBarrierFunction state is stored in Firestore." | **Redis:** `ControlBarrierFunction` uses `redis_client` to store `safety:current_cash`. | 🔴 High |
| **Policy Updates** | "Offline Pipeline... `scripts/run_transpiler_job.py`... GCS Registry." | **Partial/Unverified:** `PolicyLoader` exists, but the dynamic update loop was not verified in `src`. `PolicyLoader` reads from GCS/Local. | 🟡 Medium |
| **Sidecars** | "OPA/NeMo sidecars." | **Present:** Code attempts to connect to `http://nemo:8000` and configured OPA URL. Implementation matches. | 🟢 Low |
| **LLM Clients** | "GeminiLLM optimizes by caching `_client`." | **Verified:** `HybridClient` lazily inits `_vertex_client`. `GeminiLLM` in NeMo also implemented. | 🟢 Low |

### Recommendation
The codebase appears to be in a transition state or the "ADK Native" refactor has not been applied/committed to this branch. The system functions as a Hybrid architecture with Redis dependencies, contrary to the "Redis Removed" directive.
