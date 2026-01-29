# System Description Document: Governed Financial Advisor (GFA)

**Version:** 1.0
**Date:** January 27, 2026
**Classification:** Internal / Audit Use Only

## 1. Executive Summary

The **Governed Financial Advisor (GFA)** is an autonomous agentic system designed to research, plan, and execute financial trading strategies. Unlike standard generative AI applications, the GFA utilizes a "Hybrid Actor-Critic" architecture that strictly separates the **Generative Plane** (Reasoning/Planning) from the **Governance Plane** (Verification/Control). This separation ensures that no action is taken based solely on probabilistic generation without passing through a deterministic verification gate.

## 2. Architectural Design

The system operates on an **Actor-Critic** cognitive architecture, orchestrated via a state machine graph.

### 2.1 The Planner ("The Actor")

* **Role:** Responsible for complex reasoning, market research, and formulating trading plans.
* **Model:** Google Gemini 2.5 Flash-Lite (Fast Path) and Gemini 2.5 Pro (Reasoning Path) via Vertex AI.
* **Operation Mode:** Stochastic (Non-deterministic).
* **Key Telemetry:** Measured via `TTFT` (Time To First Token) and `TPOT` (Time Per Output Token) to track reasoning latency.

### 2.2 The Verifier ("The Critic")

* **Role:** Responsible for validating the safety, compliance, and structural integrity of the generated plan.
* **Model:** Hosted vLLM (e.g., Gemma 3-27B-Instruct) with specialized finetuning.
* **Operation Mode:** **Deterministic.** Enforces strict constraints using Finite State Machines (FSM).
* **Key Telemetry:** Measured via `risk.verification.overhead_ratio` (The "Safety Tax").

### 2.3 The Orchestrator

* **Framework:** Google ADK / LangGraph.
*   **Framework:** Google ADK / LangGraph.
*   **Function:** Manages the state and control flow. It routes "REJECTED" plans back to the Planner for correction or escalates to human review, ensuring the loop is closed and deterministic.

---

## 3. Governance & Control Mechanisms

The GFA implements a "Defense in Depth" strategy with three distinct control layers.

### 3.1 Layer 1: Mathematical Safety (CBFs)

*   **Description:** Enforces hard mathematical constraints on state transitions (invariant: `cash >= min_balance`). Calculates `h(next) >= (1-gamma) * h(current)` to guarantee safety.
*   **Control Implementation:** `ControlBarrierFunction` in `safety.py` (Redis-backed state).
*   **Audit Evidence:** Traces containing `safety.cbf_check` and `safety.barrier.h_next`.

### 3.2 Layer 2: Business Logic Policy (OPA)

*   **Description:** The `safety_check_node` checks the current proposed action against static policies (e.g., "No crypto assets for Low-Risk profiles").
*   **Control Implementation:** Open Policy Agent (OPA) via `safety_node.py`.
*   **Audit Evidence:** Traces containing `governance.opa_check` and `governance.denial_reason`.

### 3.3 Layer 3: Semantic Safety (NeMo Guardrails)

*   **Description:** Guardrails check the current prompt/response content for hallucination, jailbreaks, and off-topic deviations.
*   **Control Implementation:** NeMo Guardrails (`nemo_manager.py`).
*   **Audit Evidence:** Traces containing `guardrails.framework = "nemo"` and `risk.verdict`.

### 3.4 Layer 4: Structural Determinism (vLLM FSM)

*   **Description:** The Verifier model is mathematically constrained to produce only valid outputs (e.g., specific JSON schemas).
*   **Control Implementation:** `guided_json` / `guided_choice` parameters in vLLM.
*   **Audit Evidence:** Traces with `llm.control.fsm.enabled = True`.

---

## 4. Observability & Monitoring

The system is fully instrumented using **OpenTelemetry (OTLP)**, exporting traces to **Langfuse Cloud**.

### 4.1 Key Performance Indicators (KPIs)

| Metric | Definition | Purpose |
| --- | --- | --- |
| **Governance Rejection Rate** | % of Plans rejected by the Verifier. | Measures the alignment between the Planner and safety rules. |
| **Verification Overhead** | Latency of the Verifier / Total Workflow Latency. | Tracks the performance cost of compliance (Target: < 15%). |
| **Fallback Rate** | Frequency of switching from primary infrastructure to backup. | Indicators of infrastructure stability (ISO A.5.9). |

### 4.2 Telemetry Schema

Every system interaction generates a standardized trace with the following attributes for auditability:

* `risk.verdict`: The final decision ("APPROVED" / "REJECTED").
* `risk.rejection_source`: The specific layer that triggered the block (OPA vs. NeMo).
* `llm.control.*`: The exact parameters (Temperature, FSM constraints) used at the moment of generation.

---

## 5. ISO 42001 Compliance Matrix

This system is designed to meet the following controls of the ISO/IEC 42001:2023 standard.

| ISO Clause | Requirement | GFA Implementation Evidence |
| --- | --- | --- |
| **A.6.1.2** | **Segregation of Duties** | Separation of **Planner** (Gemini) and **Verifier** (vLLM/OPA) into distinct compute nodes and trace spans. |
| **A.8.4** | **Controllability** | Use of **vLLM FSM Modes** to enforce deterministic outputs from the Verifier, eliminating probabilistic failure modes in the safety layer. |
| **9.1** | **Monitoring & Evaluation** | Continuous monitoring of **Verification Overhead** and **Rejection Rates** via the Langfuse Dashboard. |
| **A.5.9** | **System Verification** | Every plan undergoes automated verification (`optimistic_execution_node`) before execution is attempted. |
| **7.2** | **Documented Info** | Full audit trail of every decision (Inputs, Policy Version, Verdict) stored in Langfuse with persistent Trace IDs. |

---

## 6. Infrastructure Specifications

* **Cloud Provider:** Google Cloud Platform (Vertex AI).
* **Self-Hosted Components:** vLLM Inference Server (Kubernetes/GKE), Open Policy Agent (Cloud Run).
* **Data Residency:** US-Central1 (Iowa).
* **Telemetry Storage:** Langfuse Cloud (Encrypted at rest).
