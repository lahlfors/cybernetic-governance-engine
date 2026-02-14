# Gateway Architecture: Sovereign Edition

## Overview

The Gateway acts as the central orchestrator and compliance enforcement point for the AI financial advisor. It implements a "Split-Brain" architecture, routing tasks between a high-capacity Reasoning Model (Llama 3.1 8B) and a low-latency Governance Model (Llama 3.2 3B).

## Core Components

1.  **Hybrid Gateway Service (FastAPI + FastMCP):**
    *   Exposes a unified HTTP/MCP interface.
    *   Handles tool execution requests (`execute_trade`, `search_market`).
    *   Enforces neuro-symbolic policies via OPA and the Symbolic Governor.

2.  **Sovereign vLLM Cluster:**
    *   **Node A (Reasoning):** Handles planning, complex analysis, and chain-of-thought generation.
    *   **Node B (Governance):** Handles rapid policy checks, safety filtering, and content moderation.

3.  **Observability Layer (Hybrid):**
    *   **Application Tracing (LangSmith):** Captures the execution graph, prompt templates, and tool inputs/outputs. Uses asynchronous batch processing to minimize latency.
    *   **System Monitoring (AgentSight):** An eBPF sidecar daemon that intercepts:
        *   **Encrypted Traffic (OpenSSL):** Captures raw LLM payloads at the network boundary.
        *   **System Calls (Kernel):** Monitors process creation (`execve`), file access (`openat`), and network connections (`connect`).
    *   **Correlation:** The Gateway injects the OpenTelemetry `trace_id` as an `X-Trace-Id` HTTP header into every LLM request. AgentSight uses this header to link high-level intent (LangSmith trace) with low-level system actions.

## Data Flow

1.  **User Request:** Incoming HTTP/gRPC request to the Gateway.
2.  **Policy Check (Pre-Execution):** OPA validates the request against regulatory policies.
3.  **Routing:** GatewayClient determines the target model (Reasoning vs. Governance).
4.  **Header Injection:** The client generates a trace ID and injects `X-Trace-Id`.
5.  **LLM Call:** Request is sent to vLLM. AgentSight intercepts this call.
6.  **Tool Execution:** If the model requests a tool, the Gateway executes it. AgentSight monitors the resulting system calls (e.g., network request to Alpaca API).
7.  **Logging:**
    *   Application metadata is sent asynchronously to LangSmith.
    *   System events are displayed in the AgentSight Dashboard.

## Deployment Topology

*   **Production (GKE):** Gateway runs as a service behind an Ingress. AgentSight runs as a DaemonSet or sidecar container in the same pod.
*   **Local (Docker Compose):** All components run in a shared network. See `deployment/agentsight/docker-compose.agentsight.yaml`.
