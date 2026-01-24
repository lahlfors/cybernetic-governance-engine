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

## 2. Roadmap: From "Sovereign Stack" to "Platform Native"

To maintain cloud independence (avoiding early vendor lock-in) while preparing for high-performance platform integration, we will execute a decoupled migration strategy.

### Phase 1 & 2: The "Sovereign Stack" (Cloud Independent)
**Goal:** Optimize the current stack using portable, open-source standards. This architecture works on AWS, Azure, or On-Prem.

*   **Orchestration:** `LangGraph` (Local/Containerized).
    *   *Design Principle:* **Pure Python Tools.** Tool logic must be written as standard functions, avoiding Vertex-specific SDKs. This ensures tools can be wrapped by any framework.
*   **Governance:** `OPA Sidecar` (Unix Sockets).
    *   *Tech:* Open Policy Agent binary running as a sidecar.
    *   *Optimization:* **Accept Unix Domain Sockets (UDS)** for local communication (see Section 3.5).
*   **State:** `Redis` (Persistent).
    *   *Tech:* Redis with Append Only File (AOF) enabled.

### Phase 3: The "Platform Native" Pivot (Google Cloud)
**Goal:** Leverage managed services for maximum operational maturity and global scale.

*   **Orchestration:** `Vertex AI Agent Engine`.
*   **Governance:** `OPA on Cloud Run` (Server-Side).
*   **State:** `Cloud Firestore`.

---

## 3. Strategic Analysis: The "Full-Cloud" Pivot (Phase 3)

### 3.1 The Latency Conundrum
The core value proposition of the new architecture is "Optimistic Parallel Execution" (running governance checks and tool calls simultaneously).
*   **Failure Mode:** If the Agent runs on Vertex AI (Server) but OPA runs locally (Sidecar), the "Wait-Time" explodes due to the network round-trip required for the Agent to call back to the local OPA instance.
*   **Solution:** Deploy OPA as a private Cloud Run service. This reduces the Agent-to-Policy latency to sub-millisecond levels, enabling true parallel execution.

### 3.2 Capability Gaps (STPA)
The Systems-Theoretic Process Analysis (STPA) requires stateful checks (e.g., "Has the user violated the drawdown limit 3 times?").
*   **Gap:** The proposed **Model Armor** component is a stateless "AI Firewall." It cannot replace the Causal Process Model.
*   **Remediation:** We must implement a **Validation Agent** within the ADK hierarchy that accesses the shared `Firestore` state to enforce historical constraints, effectively porting the current `RiskAnalyst` logic.

### 3.3 The Comparison Rubric

| Criteria | LangGraph (Current) | Google ADK (Target) | Verdict |
| :--- | :--- | :--- | :--- |
| **Traceability** | High (Explicit Code) | Managed (Cloud Trace) | **Neutral** (Trade control for convenience) |
| **Parallelism** | Manual (`asyncio`) | Native (`ParallelSubAgent`) | **ADK Wins** (Less boilerplate) |
| **State** | Distributed (Redis) | Unified (Firestore) | **ADK Wins** (Reduced I/O) |
| **STPA Loops** | Native (Graph Cycles) | Complex (Recursion) | **LangGraph Wins** (Easier to reason about) |

---

## 4. Tactical Improvements (Immediate Actions)

Regardless of the migration timeline, the following improvements are approved for the current codebase to resolve critical bottlenecks.

### 4.1 Async Governance Client (P0)
**Problem:** `src/governance/client.py` uses blocking `requests`, exhausting threads during optimistic execution.
**Fix:** Migrate to `httpx.AsyncClient` to allow the event loop to manage concurrency efficiently.

### 4.2 Dependency Injection (P1)
**Problem:** `src/graph/nodes/adapters.py` imports global agent instances, making unit tests fragile and dependent on external API keys.
**Fix:** Refactor agent instantiation into `create_agent()` factory functions to enable mock injection during testing.

### 4.3 Governance Circuit Breaker (P1)
**Problem:** If the OPA sidecar is down, the application hangs until timeouts occur.
**Fix:** Implement a "Fail Fast" circuit breaker. If 5 requests fail, stop querying OPA for 30s and default to `DENY` (or `SAFE_HARBOR` read-only mode).

### 4.4 Canonical Logging (P0)
**Problem:** `print()` statements obscure production debugging.
**Fix:** Adopt structured JSON logging with injected `trace_id` for correlation in Cloud Logging.

### 4.5 Unix Domain Sockets (Accepted for Phase 1/2)
**Context:** Replacing TCP/IP over localhost with Unix Domain Sockets (UDS) for sidecar communication.
**Analysis:**
*   **Pros:** Reduces syscall overhead and TCP stack latency (~10-50µs gain). Supported by OPA and `httpx`.
*   **Cons:** Incompatible with Phase 3 "Full Cloud" architecture (Network Separation).
*   **Decision:** **ACCEPT** for Phase 1 & 2 ("Sovereign Stack"). This is a high-value optimization for the current containerized architecture that aligns with the "Pure Python/Local" philosophy. It will be deprecated in Phase 3.

---

## 5. Final Recommendation

1.  **Phase 1 (Optimization):** Refactor `OPAClient` to `httpx` (with UDS support) and introduce Dependency Injection.
2.  **Phase 2 (Infrastructure):** Solidify the "Sovereign Stack" with standalone OPA and Redis containers.
3.  **Phase 3 (Migration):** Port the `RiskAnalyst` logic to an ADK `ValidationAgent` and switch orchestration to Vertex AI Agent Engine + Cloud Run OPA.

**Status:** **PROCEED** with Phase 1 immediately.
