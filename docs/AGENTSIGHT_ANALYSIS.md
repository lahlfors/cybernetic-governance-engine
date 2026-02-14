# Analysis: AgentSight vs. Application-Level Tiered Observability

## Introduction

This document analyzes the benefits and tradeoffs of adopting **AgentSight** (an eBPF-based, kernel-level observability framework) versus the current **Application-Level Tiered Observability** implementation (Python-based OTel tracing with `GenAICostOptimizerProcessor` and `ParquetSpanExporter`).

## Current Implementation (Tiered Observability)

**Mechanism:**
-   **Instrumentation:** Python OpenTelemetry (OTel) SDK.
-   **Payload Handling:** Custom `GenAICostOptimizerProcessor` intercepts spans, serializes large payloads (prompts/completions) to Parquet/S3 ("Cold Tier"), and forwards lightweight spans to Cloud Trace ("Hot Tier").
-   **Trace Correlation:** Based on explicit propagation of `trace_id` and `span_id`.

**Pros:**
-   **Context Awareness:** Deep visibility into internal application state (User ID, Session ID, specific function arguments).
-   **Self-Contained:** Does not require external daemons or privileged kernel access.
-   **Ecosystem:** Integrates seamlessly with standard OTel collectors (Jaeger, Honeycomb).

**Cons:**
-   **Performance Overhead:**
    -   **Latency:** Serializing large JSON/Parquet payloads in Python (synchronously or asynchronously on the event loop) introduces significant latency, especially for large prompts.
    -   **Resource Usage:** Consumes CPU/Memory within the application container.
-   **Maintenance Burden:** Requires maintaining custom processors, exporters, and sampling logic.
-   **Blind Spots:** Cannot observe system-level side effects (e.g., direct syscalls via `subprocess` or `os.system` that bypass instrumentation).
-   **Semantic Gap:** Sees "Intent" (prompts) but misses the "Action" (actual system behavior) unless manually instrumented.

## Proposed Implementation (Hybrid Observability)

**Strategy: "Skinny Payload" + Header Correlation + AgentSight**

Instead of turning off Python payloads entirely (which breaks LangSmith), we adopt a hybrid approach:

1.  **Application Tracing (LangSmith):**
    -   Use **Native LangSmith Tracing** (via OTel `BatchSpanProcessor`) to capture execution trees and core application context (User ID, Session ID).
    -   Utilize background threads (the default in modern OTel exporters) to minimize blocking on the main loop.
    -   Avoid custom synchronous processors (`GenAICostOptimizerProcessor`) that introduce latency.
    -   **Aggressive Sampling:** In Production, sample LangSmith traces (e.g., 1-5%) to reduce overhead, while running 100% in Dev/Staging.

2.  **System-Level Observability (AgentSight):**
    -   Use **AgentSight (eBPF)** to capture *raw* traffic (prompts/completions) and system actions (syscalls) at the kernel level.
    -   This provides full fidelity and security visibility without burdening the application process.

3.  **Correlation:**
    -   Inject the **OTel Trace ID** as an HTTP header (`X-Trace-Id`) into every LLM API request.
    -   AgentSight intercepts this header along with the payload, allowing seamless correlation between the high-level Application Trace (LangSmith) and the low-level System Trace (AgentSight).

**Pros:**
-   **Best of Both Worlds:** Retains LangSmith for prompt engineering/evaluation while leveraging AgentSight for performance and security.
-   **Low Latency:** Offloads heavy inspection to the kernel/sidecar while keeping application tracing lightweight (metadata + essential context).
-   **Security:** Detects unauthorized system calls that application tracing misses.

**Cons:**
-   **Complexity:** Requires maintaining both LangSmith integration and the AgentSight daemon.
-   **Privileged Access:** AgentSight requires `CAP_SYS_ADMIN` capabilities.

## Recommendation

**Adopt Hybrid Observability.**

1.  **Remove Custom Payload Processors:** Delete `genai_cost_optimizer.py` and `parquet_exporter.py` (Completed).
2.  **Restore Standard Tracing:** Use standard OTel `BatchSpanProcessor` to send traces to LangSmith/Jaeger asynchronously.
3.  **Inject Trace ID:** Modify the LLM client to inject `X-Trace-Id` headers.
4.  **Deploy AgentSight:** Run the AgentSight daemon alongside the application to capture full payloads and system actions.

**Action Plan:**
1.  Remove redundant files (Done).
2.  Update `telemetry.py` to restore payload capture using efficient background processors.
3.  Update `llm.py` to inject `X-Trace-Id` headers.
4.  Update Docker Compose configuration (Done).
