# Architectural Decision Record: Platform Migration & Optimization

**Status:** APPROVED
**Date:** 2024-05-22
**Context:** Comprehensive review of the "Hybrid" architecture (LangGraph + OPA) versus the proposed "Platform-Native" architecture (Google ADK + Vertex AI).

---

## 1. Executive Summary: The "Conditional Go"

The engineering team has evaluated the proposal to migrate from `LangGraph` to `Google ADK`. Our recommendation is a **CONDITIONAL GO**, contingent on a specific infrastructure pivot.

*   **Strategic Decision:** Adopt Google ADK and Vertex AI Agent Engine for Orchestration and State Management.
*   **Infrastructure Requirement:** The Policy Decision Point (OPA) **must move to Cloud Run** (Server-Side) to reside on the same network backbone as Vertex AI. A local sidecar architecture is incompatible with ADK's latency goals.
*   **Tactical Improvements:** While the migration is planned, immediate technical debt in the current codebase (Blocking I/O, Global State) must be remediated to ensure stability during the transition.

---

## 2. Strategic Migration: The "Full-Cloud" Pivot

### 2.1 The Latency Conundrum
The core value proposition of the new architecture is "Optimistic Parallel Execution" (running governance checks and tool calls simultaneously).
*   **Failure Mode:** If the Agent runs on Vertex AI (Server) but OPA runs locally (Sidecar), the "Wait-Time" explodes due to the network round-trip required for the Agent to call back to the local OPA instance.
*   **Solution:** Deploy OPA as a private Cloud Run service. This reduces the Agent-to-Policy latency to sub-millisecond levels, enabling true parallel execution.

### 2.2 Capability Gaps (STPA)
The Systems-Theoretic Process Analysis (STPA) requires stateful checks (e.g., "Has the user violated the drawdown limit 3 times?").
*   **Gap:** The proposed **Model Armor** component is a stateless "AI Firewall." It cannot replace the Causal Process Model.
*   **Remediation:** We must implement a **Validation Agent** within the ADK hierarchy that accesses the shared `Firestore` state to enforce historical constraints, effectively porting the current `RiskAnalyst` logic.

### 2.3 The Comparison Rubric

| Criteria | LangGraph (Current) | Google ADK (Target) | Verdict |
| :--- | :--- | :--- | :--- |
| **Traceability** | High (Explicit Code) | Managed (Cloud Trace) | **Neutral** (Trade control for convenience) |
| **Parallelism** | Manual (`asyncio`) | Native (`ParallelSubAgent`) | **ADK Wins** (Less boilerplate) |
| **State** | Distributed (Redis) | Unified (Firestore) | **ADK Wins** (Reduced I/O) |
| **STPA Loops** | Native (Graph Cycles) | Complex (Recursion) | **LangGraph Wins** (Easier to reason about) |

---

## 3. Tactical Improvements (Immediate Actions)

Regardless of the migration timeline, the following improvements are approved for the current codebase to resolve critical bottlenecks.

### 3.1 Async Governance Client (P0)
**Problem:** `src/governance/client.py` uses blocking `requests`, exhausting threads during optimistic execution.
**Fix:** Migrate to `httpx.AsyncClient` to allow the event loop to manage concurrency efficiently.

### 3.2 Dependency Injection (P1)
**Problem:** `src/graph/nodes/adapters.py` imports global agent instances, making unit tests fragile and dependent on external API keys.
**Fix:** Refactor agent instantiation into `create_agent()` factory functions to enable mock injection during testing.

### 3.3 Governance Circuit Breaker (P1)
**Problem:** If the OPA sidecar is down, the application hangs until timeouts occur.
**Fix:** Implement a "Fail Fast" circuit breaker. If 5 requests fail, stop querying OPA for 30s and default to `DENY` (or `SAFE_HARBOR` read-only mode).

### 3.4 Canonical Logging (P0)
**Problem:** `print()` statements obscure production debugging.
**Fix:** Adopt structured JSON logging with injected `trace_id` for correlation in Cloud Logging.

### 3.5 Unix Domain Sockets (Rejected Alternative)
**Context:** Replacing TCP/IP over localhost with Unix Domain Sockets (UDS) for sidecar communication.
**Analysis:**
*   **Pros:** Reduces syscall overhead and TCP stack latency (~10-50µs gain). Supported by OPA and `httpx`.
*   **Cons:** Only feasible if the Agent and OPA share a filesystem (Sidecar pattern). This **conflicts** with the "Full Cloud" strategy where the Agent runs on Vertex AI and OPA on Cloud Run (separated by network).
*   **Decision:** **REJECT** for Target State. While UDS is a valid optimization for the *current* containerized setup, it is incompatible with the strategic move to Vertex AI's managed runtime.

---

## 4. Final Recommendation

1.  **Phase 1 (Optimization):** Refactor `OPAClient` to `httpx` and introduce Dependency Injection.
2.  **Phase 2 (Infrastructure):** Deploy OPA policies to a private Cloud Run service.
3.  **Phase 3 (Migration):** Port the `RiskAnalyst` logic to an ADK `ValidationAgent` and switch orchestration to Vertex AI Agent Engine.

**Status:** **PROCEED** with Phase 1 immediately.
