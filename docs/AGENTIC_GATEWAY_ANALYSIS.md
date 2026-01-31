# Agentic Gateway Analysis & Refactoring Strategy

## Executive Summary

This document analyzes the architectural transition from an "In-Process Governance" model to a "Agentic Gateway" microservice pattern. The primary driver is **Code Cleanliness and Maintainability**, with a specific requirement to support **Tool Execution Interception** and **LLM Proxying**.

**Status:** The refactor has been successfully implemented. The Agentic Gateway now serves as the centralized governance point for all tool execution and LLM inference.

---

## 1. Architectural Shift

### Current State: "Agentic Gateway" (Implemented)
The `Agent` service acts as a "Pure Reasoner", computing *intent* but having no ability to *act* or *perceive* directly.

*   **North/South Traffic (User <-> Agent):** The Gateway sits in front of the Agent API, handling AuthN, Input Guardrails (NeMo), and Trace Context injection.
*   **East/West Traffic (Agent <-> World):**
    *   **LLM Proxy:** Agent sends `(messages, model_config)` to Gateway. Gateway handles token counting, DLP, caching, and provider routing.
    *   **Tool Execution Proxy:** Agent sends `(tool_name="execute_trade", params={...})` to Gateway. Gateway checks Policy (OPA), Safety (CBF), Consensus, and *then* executes the tool.

### Key Implementation Details
1.  **Async/Await Architecture:** The Gateway uses `async def` for all tool executions to prevent blocking the gRPC event loop, adhering to the "Latency as Currency" requirement.
2.  **Dry Run Capability:** The Gateway supports a `dry_run` flag in `ExecuteTool`. This allows the **Evaluator Agent** (System 3) to verify if an action *would* be allowed by Policy (OPA) and Safety (CBF) without actually executing it.
3.  **Market Service Stub:** Market data checks are routed through a `MarketService` within the Gateway, allowing for centralized simulation or real API integration.

---

## 2. Component Migration Plan (Completed)

| Component | Current Location | New Location (Gateway) | Notes |
| :--- | :--- | :--- | :--- |
| **HybridClient** | `infrastructure/llm_client.py` | `gateway/core/llm.py` | Gateway acts as the "Model Router". |
| **OPAClient** | `governance/client.py` | `gateway/core/policy.py` | Policy checks are enforced strictly at the Gateway. |
| **Tool Logic** | `tools/trades.py` | `gateway/core/tools.py` | The Agent code only contains stubs. Execution logic resides in the Gateway. |
| **Safety Logic** | `evaluator/agent.py` | `gateway/server/main.py` | Mocks removed. Evaluator calls Gateway for `check_market_status`, `verify_policy_opa`, and `verify_content_safety`. |

---

## 3. Protocol Analysis

**Decision: gRPC (Protobuf)**
The system uses gRPC for high-performance, strongly-typed communication between the Agent and the Gateway.

*   **LLM Streaming:** Supported via `stream ChatResponse`.
*   **Tool Calls:** Strongly typed via `ToolRequest` and `ToolResponse`.
*   **Security:** Cloud Run Service-to-Service authentication (OIDC) is supported via `GatewayClient`.

---

## 4. Latency Impact Evaluation

**The "Tax" of Separation:**
*   **Network Hop:** ~0.2ms - 0.5ms per call (localhost/UDS).

**The "Dividend" of Separation:**
*   **Non-Blocking IO:** The Gateway handles heavy governance checks asynchronously.
*   **Connection Pooling:** Persistent connections to VertexAI and OPA.
*   **Dry Run Simulation:** Allows "Optimistic Planning" (Agent) with "Pessimistic Verification" (Evaluator) without risk of accidental execution.

---

## 5. Final Recommendation

**Refactor Complete.**
The system now adheres to the Agentic Gateway pattern. All future tool integrations should be added to `src/gateway/core/tools.py` and registered in `src/gateway/server/main.py`.
