# Proposal: Refactoring Agentic Gateway to MCP & A2A Protocols

## Executive Summary
This document analyzes the feasibility and strategy for refactoring the current **gRPC/HTTP Agentic Gateway** to utilize the **Model Context Protocol (MCP)** and standardized **Agent-to-Agent (A2A)** communication patterns. This move aligns with the "Sovereign Stack" initiative by adopting open standards for tool interoperability and agent orchestration.

## 1. The Problem
*   **Proprietary Protocols:** The current Gateway uses a custom gRPC definition (`gateway.proto`) for `ExecuteTool` and `Chat`. This limits interoperability with external tools or agents not built with our specific SDK.
*   **Tightly Coupled Agents:** Agents currently communicate via `google.adk.tools.transfer_to_agent`, implying a monolithic, in-process runtime. Scaling to distributed agents (e.g., running the Risk Analyst on a separate secure enclave) requires a standardized over-the-wire protocol.

## 2. The Solution: MCP as the Universal Interface

### 2.1. Gateway as an MCP Server
The **Agentic Gateway** (currently exposing `ExecuteTool`) should be refactored into an **MCP Server**.
*   **Mapping:**
    *   `ExecuteTool(tool_name, params)` -> MCP `CallToolRequest`.
    *   `ListTools` -> MCP `ListToolsRequest`.
*   **Benefits:**
    *   Any MCP-compliant LLM client (e.g., Claude Desktop, Zed, or our own custom Client) can instantly access the Gateway's governed tools (Trade, Market Data) without custom integration code.
    *   Governance (OPA, NeMo) remains implemented as "Middleware" within the MCP Server logic, invisible to the client but strictly enforced.

### 2.2. Agents as MCP Servers (A2A)
Instead of "transferring" control via in-memory objects, we treat each specialized agent as a distinct **MCP Server** exposing high-level "Tools".

| Current Agent | Proposed MCP Server | Exposed Tool |
| :--- | :--- | :--- |
| **Data Analyst** | `data-analyst-server` | `generate_market_report(ticker)` |
| **Governed Trader** | `trader-server` | `execute_strategy(plan)` |
| **Risk Analyst** | `risk-server` | `audit_plan(plan)` |

The **Coordinator Agent** (Supervisor) acts as the **MCP Client**. It connects to these servers and "calls" the agents as if they were functions.

## 3. Implementation Plan

### Phase 1: Gateway Conversion (Control Plane)
1.  **Dependency:** Add `mcp` SDK to `pyproject.toml`.
2.  **Refactor:** Rewrite `src/gateway/server/main.py` to initialize an `mcp.server.fastmcp.FastMCP` instance instead of a gRPC server.
3.  **Transport:** Support `stdio` (for local composition) and `SSE` (Server-Sent Events) for networked deployment.
4.  **Governance:** Port the OPA/NeMo interceptors to wrap the MCP tool handlers.

### Phase 2: Agent Decoupling (Reasoning Plane)
1.  **Service Wrappers:** Create lightweight `mcp` wrappers around existing Agent classes.
2.  **Orchestrator:** Update the `Financial Advisor` (Coordinator) to use an `MCPClient` to discover and call these remote agent tools.

## 4. Pros & Cons

### Pros
*   **Interoperability:** Compatible with the growing ecosystem of MCP tools and IDEs.
*   **Modularity:** Agents can be written in any language (TypeScript, Python, Go) as long as they speak MCP.
*   **Security:** MCP supports distinct connection transports; highly sensitive agents (Risk) can run over isolated stdio pipes.

### Cons
*   **Latency:** Moving from in-process `transfer_to_agent` to HTTP/SSE/Stdio serialization adds latency (milliseconds).
    *   *Mitigation:* Use Stdio for local agents; acceptable for the < 200ms budget if optimized.
*   **Complexity:** Managing multiple MCP server processes vs one Monolith.

## 5. Feasibility Verdict
**HIGHLY FEASIBLE.**
The current codebase already separates "Tools" (`src/gateway/core/tools.py`) from "Agents". Wrapping these tools in MCP is a direct refactor. The Governance logic (OPA/NeMo) maps cleanly to MCP Tool Interceptors.

## 6. Next Steps
1.  Approve this proposal.
2.  Create a prototype branch `refactor/mcp-gateway`.
3.  Implement the Gateway MCP Server.
