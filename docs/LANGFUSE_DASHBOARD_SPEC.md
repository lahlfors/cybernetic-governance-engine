# Langfuse Dashboard Specification: Governed Financial Advisor

**Version:** 1.0
**Target Audience:** Compliance Officers, System Architects, Auditors
**Purpose:** Provides step-by-step instructions to configure Langfuse Dashboards that visualize the "Actor-Critic" architecture and satisfy ISO 42001 monitoring requirements.

---

## 1. Dashboard: "ISO 42001 Compliance Overview"

**Goal:** Provide a high-level "Traffic Light" view of system safety and determinism for non-technical stakeholders (Clause 9.1).

### Widget 1: Safety Gate Reliability (The "Stop" Sign)
*   **Question Answered:** "How often is the AI actively blocking unsafe actions?"
*   **Type:** Number (Percentage)
*   **Metric:** Rejection Rate
*   **Filter:** `span.name` = "risk.verification.combined"
*   **Aggregation:** Count of spans where `risk.verdict` = "REJECTED" / Total Count
*   **ISO Evidence:** Proves the "Controllability" mechanism (A.8.4) is active, not passive.

### Widget 2: Deterministic Control Coverage
*   **Question Answered:** "Are we enforcing strict structural rules (FSM) on critical decisions?"
*   **Type:** Number (Percentage)
*   **Metric:** FSM Utilization Rate
*   **Filter:** `span.name` = "hybrid_generate" AND `llm.type` = "verifier"
*   **Aggregation:** Count where `llm.control.fsm.enabled` = `true` / Total Verifier Calls
*   **Target:** 100% (Any drop below 100% is a compliance breach).

### Widget 3: Policy Violation Breakdown
*   **Question Answered:** "What specific rules are stopping the AI?"
*   **Type:** Bar Chart
*   **Metric:** Count by Rejection Source
*   **Filter:** `span.name` = "risk.verification.combined" AND `risk.verdict` = "REJECTED"
*   **Group By:** `risk.rejection_source` (Values: "opa", "nemo")
*   **ISO Evidence:** Distinguishes between "Business Logic Violations" (OPA) and "Safety Violations" (NeMo) (A.5.9).

---

## 2. Dashboard: "Performance & 'Safety Tax'"

**Goal:** Quantify the latency cost of running the "Critic" (Verifier) alongside the "Actor" (Planner).

### Widget 1: The "Safety Tax" Ratio
*   **Question Answered:** "How much slower is the system because of our safety checks?"
*   **Type:** Line Chart (Time Series)
*   **Metric:** Average Overhead Ratio
*   **Filter:** `span.name` = "workflow.execution"
*   **Y-Axis:** Average of `risk.verification.overhead_ratio`
*   **Target:** < 0.15 (15%)

### Widget 2: Latency Decomposition (Stacked Area)
*   **Question Answered:** "Where is the time going?"
*   **Type:** Stacked Area Chart
*   **Metric:** P95 Latency
*   **Series 1 (Planner):** `span.name` = "hybrid_generate" AND `llm.type` = "planner" (Generation Time)
*   **Series 2 (Verifier):** `span.name` = "risk.verification.combined" (Verification Time)
*   **X-Axis:** Time

### Widget 3: Planner Responsiveness (TTFT)
*   **Question Answered:** "Does the user feel a delay?"
*   **Type:** Number (P95)
*   **Metric:** P95 Time To First Token
*   **Filter:** `span.name` = "hybrid_generate" AND `llm.type` = "planner"
*   **Value:** `telemetry.ttft_ms`

---

## 3. Dashboard: "Audit Trail & Forensics"

**Goal:** Enable deep-dive investigation into specific incidents.

### Widget 1: FSM Constraint Drift
*   **Question Answered:** "Did the JSON Schema for verification change?"
*   **Type:** Table
*   **Metric:** Count of Unique Constraints
*   **Filter:** `span.name` = "hybrid_generate" AND `llm.control.fsm.mode` = "json_schema"
*   **Group By:** `llm.control.fsm.constraint` (The Hash)
*   **Analysis:** You should only see *one* active hash per deployment version. Multiple hashes indicate configuration drift.

### Widget 2: Fallback Stability
*   **Question Answered:** "How often is the primary vLLM failing?"
*   **Type:** Line Chart
*   **Metric:** Fallback Count
*   **Filter:** `span.name` = "llm.fallback.vertex"
*   **Aggregation:** Count over time.
*   **ISO Evidence:** Demonstrates monitoring of system availability and resilience (A.5.9).

---

## 4. Implementation Notes

### Metric Mapping Table

| UI Concept | OpenTelemetry Attribute Key | Source Code Location |
| :--- | :--- | :--- |
| **Verification Span** | `risk.verification.combined` | `src/.../graph/nodes/optimistic_nodes.py` |
| **Verdict** | `risk.verdict` | `src/.../graph/nodes/optimistic_nodes.py` |
| **Overhead Ratio** | `risk.verification.overhead_ratio` | `src/.../graph/nodes/optimistic_nodes.py` |
| **FSM Enabled** | `llm.control.fsm.enabled` | `src/.../infrastructure/llm_client.py` |
| **Constraint Hash** | `llm.control.fsm.constraint` | `src/.../infrastructure/llm_client.py` |
| **TTFT** | `telemetry.ttft_ms` | `src/.../infrastructure/llm_client.py` |
