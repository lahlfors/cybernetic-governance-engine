# 🎬 Governed Financial Advisor - Demo Script

This script guides you through demonstrating the **Governed Financial Advisor**, highlighting its "Green Stack" architecture, Real-time Guardrails (NeMo), and Deep Observability (OpenTelemetry/Vertex AI).

---

## 🛠️ Prerequisites

1.  **Backend:** Ensure the FastAPI server is running.
    ```bash
    export PYTHONPATH=$PYTHONPATH:.
    python src/server.py
    ```
2.  **Frontend:** Ensure the Streamlit UI is running.
    ```bash
    python -m streamlit run ui/app.py --server.port 8501
    ```
3.  **Permissions:** Ensure your environment has `GOOGlE_APPLICATION_CREDENTIALS` set with access to Vertex AI and Cloud Trace.

---

## 🎭 Scenario 1: The "Safe" Happy Path
**Goal:** Demonstrate the system working normally under safe conditions.

1.  **UI Action:** Open the Streamlit App (`http://localhost:8501`).
2.  **Demo Panel:** In the sidebar "🛠️ Demo Control Panel", click **"✅ Normal Operation"**.
3.  **Chat Action:** Type: *"Execute a market buy order for 100 shares of GOOGL."*
4.  **Observation:**
    *   The Agent accepts the order.
    *   **NeMo Guardrails:** The internal checks (`check_approval_token`, `check_data_latency`) pass silently.
    *   **Trace:** Click the **"🔍 [View Trace]"** link below the response. It opens Google Cloud Trace.
    *   **Show:** In the Trace timeline, expand the spans to show `check_data_latency` completing in <1ms.

---

## 🎭 Scenario 2: Fault Injection (Latency Guardrail)
**Goal:** Demonstrate the **Safety Layer (L3)** blocking a risk that the LLM might ignore. We simulate a "High Frequency Trading" constraint violation.

1.  **Demo Panel:** Click **"🐢 High Latency (>200ms)"**.
    *   *What happens:* The system injects artificial latency into the governance check, simulating stale market data.
2.  **Chat Action:** Type: *"Execute a market buy order for 100 shares of GOOGL."*
3.  **Observation:**
    *   **Refusal:** The Agent (via Guardrails) refuses the trade: *"I cannot execute this trade due to high data latency."*
    *   **Trace:** Click **"🔍 [View Trace]"**.
    *   **Show:**
        *   Find the span `check_data_latency`.
        *   Note the duration is >200ms.
        *   Show the log/event indicating **"⛔ UCA Violation (Latency)"**.
    *   *Key Takeaway:* The LLM didn't decide to stop; the **deterministic code** (System 2) forced it to stop.

---

## 🎭 Scenario 3: Green Stack Governance (Vertex AI)
**Goal:** Demonstrate the **Policy Layer (L2)**. We will trigger the "Offline Risk Analyst" to discover new risks and compile them into code.

1.  **Demo Panel:** Scroll to "Green Stack Governance".
2.  **UI Action:** Click **"☁️ Run Green Stack on Vertex AI"**.
3.  **Observation:**
    *   A toast message appears: *"Vertex Submission Initiated"*.
    *   The "Pipeline Status" indicator updates to `submitting` -> `submitted`.
    *   A link appears: **"☁️ [View Vertex Pipeline]"**.
4.  **Vertex AI Dashboard:**
    *   Click the link to open the Vertex AI Pipelines UI.
    *   **Show:** The graph visualization: `risk-discovery-op` -> `policy-transpilation-op` -> `rule-deployment-op`.
    *   **Drill Down:** Click on `risk-discovery-op` -> "Logs". Show the "Risk Analyst" agent reasoning about the strategy.
    *   **Drill Down:** Click on `policy-transpilation-op` -> "Logs". Show the Python code being generated from the identified UCAs.

---

## 🧹 Reset
To return to normal:
1.  Click **"✅ Normal Operation"** in the Demo Control Panel.
