# 🎬 How to Demo: Agentic Observability

This guide explains how to run the observability demo script and visualize the "Governor's Ledger" in Langfuse.

## 📋 Prerequisites

1.  **Environment**: Python 3.10+ with project dependencies installed.
2.  **Infrastructure**: Redis must be running (used for safety state).
    ```bash
    # Local via Docker
    docker run -d -p 6379:6379 redis:latest
    ```
3.  **Observability**: Application must be configured to send traces to the OpenTelemetry Collector on GKE, which forwards to Langfuse.
    - Ensure `.env` has `ENABLE_LOGGING=true`. The system routes telemetry automatically in K8s.

## 🚀 Running the Demo Script

The script `src/governed_financial_advisor/demo/demo_observability.py` orchestrates three specific scenarios designed to light up your analytics widgets.

Run it from the project root:

```bash
python3 src/governed_financial_advisor/demo/demo_observability.py
```

### What Happens?

The script simulates 3 different users executing trades:

1.  **Scenario 1: The Happy Path ("Currency Ledger")**
    *   **User:** `demo_user_happy`
    *   **Action:** Buys $1,000 AAPL.
    *   **Outcome:** ✅ Allowed.
    *   **Metric:** Generates valid "Reasoning Spend" and minimal "Governance Tax".

2.  **Scenario 2: The Policy Violation ("Wall Impact")**
    *   **User:** `demo_user_risky`
    *   **Action:** Tries to buy $20,000 TSLA (Junior limit is $5,000).
    *   **Outcome:** 🛑 Blocked by OPA.
    *   **Metric:** Increments "Rejected" count for `governance.policy_id`.

3.  **Scenario 3: The Bankruptcy ("Safety Valve")**
    *   **User:** `demo_user_spender`
    *   **Action:** Repeatedly buys $4,500 batches of GOOGL.
    *   **Outcome:** 💸 Drains cash reserve -> Triggers Bankruptcy Protocol.
    *   **Metric:** Emits `event.bankruptcy=True` and `safety.bankruptcy_deficit`.

---

## 📊 Verifying in Langfuse

Navigate to your Langfuse Dashboard and check the **Agentic DevOps** board.

### Widget 1: The Currency Ledger (Tax vs. Spend)
*   **Look for:** A stacked area chart showing request duration.
*   **What you see:**
    *   **Green Area (Reasoning):** Time spent in `reasoning.execution` (Agent thinking).
    *   **Red Area (Tax):** Time spent in `governance.opa_check` (Policy verification).
*   **Goal:** Ensure the "Tax" layer is thin compared to "Reasoning".

### Widget 2: The Wall Impact (Friction)
*   **Look for:** A bar chart grouped by Policy ID.
*   **Data:** Filtered for `governance.verdict = REJECTED`.
*   **Insight:** You should see a bar for **"Finance-Limit-Junior"** (or similar OPA rule ID) from Scenario 2.

### Widget 3: The Bankruptcy Monitor
*   **Look for:** A big number widget (Stat).
*   **Filter:** `event.bankruptcy = True`.
*   **Value:** Should be **> 0** (Red Alert).
*   **Insight:** Indicates the Control Barrier Function (CBF) successfully intervened to prevent total ruin.

---

## Troubleshooting

*   **No Traces?** Check that the `otel-collector` and `gateway` pods are running in GKE, and `ENABLE_LOGGING=true`.
*   **Redis Error?** Ensure Redis is running on port 6379.
*   **Wrong Attributes?** Verify the spans in Langfuse "Traces" view have attributes starting with `governance.` and `safety.`.
