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

## Proposed Implementation (AgentSight)

**Mechanism:**
-   **Instrumentation:** eBPF (kernel probes) on syscalls (`openat`, `execve`, etc.) and SSL/TLS traffic (`SSL_read`, `SSL_write`).
-   **Payload Handling:** Captures encrypted traffic at the kernel/library boundary (OpenSSL), correlating it with process lineage.
-   **Trace Correlation:** Uses process lineage (fork/exec) and temporal proximity to link Intent to Action.

**Pros:**
-   **Zero Instrumentation:** Requires no code changes in the Python application.
-   **Performance:**
    -   **Low Overhead:** Offloads heavy payload capturing to the kernel/sidecar (<3% overhead claimed).
    -   **Parallelism:** Does not block the application's event loop.
-   **Security:** Detects unauthorized system calls (e.g., shell commands) that application-level tracing might miss.
-   **Bridging the Semantic Gap:** Automatically correlates high-level Intent (Prompt) with low-level Action (Syscall).

**Cons:**
-   **Complexity:** Requires privileged access (`CAP_SYS_ADMIN`) and kernel headers, which can be challenging in managed environments (e.g., GKE Autopilot).
-   **Loss of Application Context:** May lose internal application variables unless they are exposed via network headers or logs.
-   **External Dependency:** Relies on the AgentSight daemon being present and healthy.

## Recommendation

**Adopt AgentSight principles and Remove Application-Level Payload Capture.**

To improve system latency and reduce complexity, we should remove the custom `GenAICostOptimizerProcessor` and `ParquetSpanExporter`. Instead, we should rely on:

1.  **Lightweight Tracing:** Keep standard OTel tracing for timing and causal links (`trace_id`, `span_id`), but **stop capturing heavy payloads** (prompts/completions) in the Python process.
2.  **System-Level Observability:** Delegate payload capture and security monitoring to AgentSight (or a similar sidecar) running alongside the application.

**Action Plan:**
1.  Remove `src/governed_financial_advisor/infrastructure/telemetry/processors/genai_cost_optimizer.py`.
2.  Remove `src/governed_financial_advisor/infrastructure/telemetry/exporters/parquet_exporter.py`.
3.  Simplify `src/governed_financial_advisor/utils/telemetry.py` to use standard OTLP/Cloud Trace exporters without payload capture.
4.  Remove heavy dependencies (`pandas`, `pyarrow`, `fastparquet`) from `pyproject.toml`.
