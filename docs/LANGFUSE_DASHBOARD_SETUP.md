# Agentic DevOps: Currency Dashboard (Langfuse Setup)

This guide outlines how to configure **Langfuse** to visualize the "Latency as Currency" economy defined in our feasibility study.

## 1. Prerequisites
Ensure the application is sending telemetry to Langfuse via the OpenTelemetry exporter.
*   `LANGFUSE_PUBLIC_KEY`
*   `LANGFUSE_SECRET_KEY`
*   `LANGFUSE_BASE_URL`

## 2. Metrics to Track

The following metrics are automatically populated by the `OPAClient` and `HybridClient` instrumentation.

### A. Governance Tax (The Cost of Safety)
*   **Metric:** `latency_currency_tax` (Span Attribute)
*   **Source:** `governance.opa_check` spans.
*   **Langfuse Chart:**
    *   **Type:** Analytic (Line Chart)
    *   **Filter:** `name` = "governance.opa_check"
    *   **Value:** Average of `latency_currency_tax`
    *   **Group By:** `governance.action` (Optional)

### B. Reasoning Spend (The Investment)
*   **Metric:** `telemetry.total_generation_time_ms`
*   **Source:** `hybrid_generate` spans where `llm.mode` = "planner".
*   **Langfuse Chart:**
    *   **Type:** Analytic (Line Chart)
    *   **Filter:** `llm.mode` = "planner"
    *   **Value:** Average of `telemetry.total_generation_time_ms`

### C. Bankruptcy Rate (The Failure)
*   **Metric:** `circuit_breaker_bankruptcy_total` (Simulated via log events or span status)
*   **Source:** Logs with message containing "Bankruptcy Protocol Triggered".
*   **Langfuse Chart:**
    *   **Type:** Event Count
    *   **Filter:** Level = "Critical" AND Message contains "Bankruptcy"

## 3. Creating the Dashboard

1.  Log in to your Langfuse Project.
2.  Navigate to **Dashboard**.
3.  Click **+ Add Chart**.
4.  Select **Trace Analytics**.
5.  **Chart 1: The Currency Ledger**
    *   Y-Axis: `p95(latency_currency_tax)` (The Tax) vs `p95(generation_time)` (The Spend).
    *   Goal: Ensure Tax < 15% of Spend.
6.  **Chart 2: The Wall Hits**
    *   Y-Axis: Count of Traces where `tool.outcome` = "BLOCKED_OPA".
    *   Goal: Monitor rejection rate spikes (need for policy tuning).

## 4. Alerting
Set up alerts in Langfuse (or connected PagerDuty) for:
*   **Inflation Alert:** If `latency_currency_tax` > 200ms (p50).
*   **Bankruptcy Alert:** Any occurrence of "Bankruptcy Protocol Triggered".
