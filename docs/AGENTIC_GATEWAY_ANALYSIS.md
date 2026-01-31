# Agentic Gateway Analysis & Refactoring Strategy

## Executive Summary

This document analyzes the architectural transition from an "In-Process Governance" model to a "Agentic Gateway" microservice pattern. The primary driver is **Code Cleanliness and Maintainability**, with a specific requirement to support **Tool Execution Interception** and **LLM Proxying**.

**Recommendation:** Implement a **gRPC-based Sidecar Service** (The Gateway) that acts as the exclusive interface for all external IO (LLM calls) and Effect Execution (Tools).

---

## 1. Architectural Shift

### Current State: "Fat Agent"
Currently, the `Agent` service (in `src/governed_financial_advisor/`) is responsible for:
1.  **Reasoning:** Generating plans/prompts.
2.  **Infrastructure:** Managing `HybridClient` (Vertex/vLLM connections).
3.  **Governance:** Running `OPAClient` and `CircuitBreaker` logic locally.
4.  **Execution:** Directly importing and running `src.tools.trades.execute_trade`.

**Problems:**
*   **Coupling:** Business logic is mixed with infrastructure/policy code.
*   **Security:** If the Agent is compromised, it has direct access to `execute_trade` code.
*   **Observability:** Tracing is scattered across clients (`client.py`, `llm_client.py`).

### Proposed State: "Agentic Gateway"
The Agent becomes a "Pure Reasoner". It computes *intent* but has no ability to *act* or *perceive* directly.

*   **North/South Traffic (User <-> Agent):** The Gateway sits in front of the Agent API, handling AuthN, Input Guardrails (NeMo), and Trace Context injection.
*   **East/West Traffic (Agent <-> World):**
    *   **LLM Proxy:** Agent sends `(messages, model_config)` to Gateway. Gateway handles token counting, DLP, caching, and provider routing.
    *   **Tool Execution Proxy:** Agent sends `(tool_name="execute_trade", params={...})` to Gateway. Gateway checks Policy (OPA), Safety (CBF), Consensus, and *then* executes the tool.

---

## 2. Component Migration Plan

The following components will be refactored out of the Agent service and into the Gateway:

| Component | Current Location | New Location (Gateway) | Notes |
| :--- | :--- | :--- | :--- |
| **HybridClient** | `infrastructure/llm_client.py` | `gateway/llm/client.py` | Gateway becomes the "Model Router". Agent just requests "System 1" or "System 2" capabilities. |
| **OPAClient** | `governance/client.py` | `gateway/policy/opa.py` | Policy checks are enforced strictly at the Gateway. The Agent cannot bypass them. |
| **CircuitBreaker** | `governance/client.py` | `gateway/resilience/breaker.py` | Global stability managed at the edge. |
| **Tool Logic** | `tools/trades.py` | `gateway/tools/trades.py` | **Major Change:** The Agent code will *no longer contain the trade execution logic*. It will only have interface definitions (Stubs). |
| **NeMo Rails** | `server.py` | `gateway/rails/nemo.py` | Input/Output rails move to the entry point. |

---

## 3. Protocol Analysis & Recommendation

The requirement is "Most Efficient Protocol".

### Option A: HTTP/REST (FastAPI)
*   **Format:** JSON.
*   **Pros:** Human-readable, standard ecosystem, easy to debug.
*   **Cons:** Verbose (text-based), higher serialization/deserialization overhead, HTTP/1.1 connection management overhead (unless HTTP/2 is forced).

### Option B: gRPC (Protobuf)
*   **Format:** Binary (Protobuf).
*   **Pros:**
    *   **Efficiency:** Smaller payloads, faster serialization.
    *   **Streaming:** Native bidirectional streaming (perfect for LLM token streaming).
    *   **Strict Contracts:** `.proto` files define the interface rigorously (Input/Output types).
    *   **Performance:** HTTP/2 by default (multiplexing, persistent connections).
*   **Cons:** Requires build step (`protoc`), slightly higher complexity to set up.

### Recommendation: gRPC
Given the "Latency as Currency" philosophy and the need to proxy **LLM Streams** and **RPC Tool Calls**, **gRPC is the superior choice**.

*   **LLM Streaming:** gRPC streaming is far more robust than HTTP Chunked Transfer Encoding for relaying LLM tokens from `Provider -> Gateway -> Agent`.
*   **Type Safety:** Defining Tool Interfaces in Protobuf ensures the Agent and Gateway strictly agree on valid parameters, reducing runtime errors.

---

## 4. Latency Impact Evaluation

**The "Tax" of Separation:**
*   **Network Hop:** Moving from In-Process function calls to `localhost` gRPC adds **~0.2ms - 0.5ms** per call.
*   **Serialization:** Protobuf serialization is neglible (<0.1ms).

**The "Dividend" of Separation:**
*   **Connection Pooling:** The Gateway can maintain persistent, warm connections to VertexAI/vLLM and OPA, avoiding the "cold start" of HTTP clients in transient Agent processes.
*   **Parallelism:** The Gateway can offload "Safety Checks" (Consensus, OPA) asynchronously while the Agent is doing other work (if the protocol supports async ack).

**Net Impact:**
*   For **LLM Calls:** Neutral. The overhead of the network hop is invisible compared to the 20ms+ TTFT of the LLM.
*   For **Tool Calls:** Slight Increase (~1ms). This is acceptable given the **Security** and **Governance** gains. The "Governance Tax" (OPA check) is already ~10ms; adding 1ms for the network is a 10% increase on the tax, but a 0.01% increase on the total transaction time.

---

## 5. Pros & Cons Summary

### Pros (Why do this?)
1.  **Hard Security Boundary:** The Agent literally *cannot* execute a trade. It can only *ask* the Gateway. If the Gateway's policy says "NO", code execution is physically impossible.
2.  **Centralized Observability:** A single interceptor for all Token Usage, Costs, and Policy Decisions. No more "did we instrument that new agent?" worries.
3.  **Simpler Agents:** Agent code becomes purely prompt management and state handling. Infrastructure complexity is stripped away.
4.  **Language Agnostic:** The Gateway can be written in Go/Rust for extreme performance later, while Agents stay in Python for flexibility.

### Cons (The Cost)
1.  **Complexity:** Running two services instead of one.
2.  **Development Friction:** changing a tool requires updating the Gateway (implementation) AND the Agent (interface/proto).
3.  **Debugging:** "Trace Context" propagation becomes critical. You can't just use a debugger breakpoint across the process boundary.

## 6. Final Recommendation

**Proceed with the "Agentic Gateway" refactor using gRPC.**

1.  **Define `.proto` Service:**
    *   `service Gateway { rpc ExecuteTool(ToolRequest) returns (ToolResponse); rpc Chat(StreamRequest) returns (stream StreamResponse); }`
2.  **Extract Core Logic:** Move `HybridClient` and `OPAClient` to `src/gateway/`.
3.  **Implement Gateway:** Create a standard gRPC server (using `grpcio`).
4.  **Stub Agents:** Replace `FunctionTool(execute_trade)` in the Agent with a `GrpcTool(remote_stub.ExecuteTool)`.
