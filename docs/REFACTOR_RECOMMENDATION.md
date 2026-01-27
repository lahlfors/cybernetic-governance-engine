# Refactor Recommendation: Hybrid Native Architecture

## Executive Summary
This document outlines the strategy to refactor the "Sovereign Stack" into a **Hybrid Native** architecture that exclusively leverages Google Cloud Platform (GCP) and Vertex AI services where available, minimizing self-hosted dependencies (local Redis, sidecars) while preserving the high-performance hybrid inference model.

## 1. Orchestration: From LangGraph to ADK Supervisor

### Current State
*   **LangGraph**: Manages state transitions (Coordinator -> Data Analyst -> Risk -> etc.) via hard-coded conditional edges.
*   **ADK**: Used only as "Agent implementations" wrapped inside graph nodes.
*   **Pros**: Deterministic, visualizable.
*   **Cons**: Requires a custom runtime (FastAPI + LangGraph) and Redis for checkpointing.

### Proposed State (Vertex Reasoning Engine)
*   **ADK Supervisor**: The `financial_coordinator` agent becomes the true root. It uses the `route_request` tool (calling `transfer_to_agent`) to hand off control to sub-agents.
*   **Runtime**: The entire agent swarm runs within the **Vertex AI Reasoning Engine** (or a simplified Cloud Run container using the ADK Runner loop directly).
*   **Determinism**: We rely on the `route_request` tool implementation. To ensure the "rigid process" requested, the Supervisor's prompt will be reinforced with a "Process Map" that strictly dictates the allowed transitions (e.g., *Always* route to Risk Analyst after Execution Analyst).

**Recommendation**: **Proceed**. The `google-adk` library's `transfer_to_agent` mechanism is sufficient to replicate the hub-and-spoke workflow.

## 2. State Management: Removing Redis

### Current State
*   **Redis**: Used for LangGraph `checkpoints` (conversation history persistence) and potentially simple caching.
*   **Cons**: Adds infrastructure complexity (VPC connectors, maintenance).

### Proposed State
*   **Vertex AI Session / Firestore**: We will implement a `FirestoreSessionService` (or use the native Vertex Session if applicable) that adheres to the ADK `SessionService` interface.
*   **Benefit**: Serverless, managed state.

**Recommendation**: **Proceed**. Replace `InMemorySessionService` (dev) and Redis (prod) with a GCP-native implementation.

## 3. Governance: Decoupling OPA

### Current State
*   **Sidecar (UDS)**: OPA runs in the same pod/container, communicating via Unix Domain Socket. Latency is negligible (<1ms).

### Proposed State
*   **Standalone Service**: OPA runs as a separate Cloud Run service.
*   **Trade-off**: Adds network latency (~10-20ms internal).
*   **Mitigation**: The `OPAClient` already implements a `CircuitBreaker`. We will tune the timeouts to be slightly more tolerant.

**Recommendation**: **Proceed**. This allows the main agent to be deployed to environments that do not support sidecars (like standard Vertex Reasoning Engine) while keeping policy logic centralized.

## 4. Compute: Hybrid Inference

### Strategy
*   **Reasoning (System 2)**: Remains on **Gemini-1.5-Pro** (via Vertex AI).
*   **Tactical (System 1)**: Remains on **Gemma/Llama** (via GKE/vLLM).
*   **Change**: The "Fast Path" client (vLLM) will be kept, but we will ensure it communicates with the GKE cluster service endpoint.

## Final Plan

1.  **Infrastructure**: Remove Redis from `docker-compose`. Isolate OPA.
2.  **Code**:
    *   Implement `src/infrastructure/vertex_session.py`.
    *   Refactor `src/server.py` to use `Runner(agent=root_agent)` instead of `graph.invoke()`.
    *   Update `src/governance/client.py` for remote OPA.
3.  **Deployment**: Create `deployment/vertex_reasoning_engine/` configuration.

**Verdict**: The refactor aligns perfectly with the "exclusively GCP/Vertex native" goal without regressing safety (via OPA) or speed (via Hybrid Compute).
