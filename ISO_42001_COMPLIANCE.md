# ISO/IEC 42001 compliance: Telemetry Audit Map

## Overview
This document analyzes how the **Cybernetic Governance Engine's** telemetry implementation (`Google Cloud Trace`) supports compliance with **ISO/IEC 42001 (Artificial Intelligence Management System)**.

The system uses **OpenTelemetry** to generate immutable trace records for every agent action, specifically instrumenting the "Governance Layer" to provide auditability for AI decision-making.

## Compliance Matrix

The following table maps ISO 42001 controls to specific trace attributes captured by the system.

| ISO 42001 Control | Requirement | System Evidence (Trace Span) | Attribute / Value | Status |
| :--- | :--- | :--- | :--- | :--- |
| **A.10.1** | **Transparency & Explainability** | `governance.check` | `governance.decision`=`ALLOW`\|`DENY` | ✅ **Fully Compliant**. Every tool execution is strictly correlated with a policy decision. |
| **A.8.4** | **AI System Impact Assessment** | `consensus.check` | `consensus.votes`=`['APPROVE', 'REJECT']` | ✅ **Compliant**. High-stakes decisions record the internal "debate" and voting logic of the safety agents. |
| **A.6.2.8** | **Event Logging** | `guardrail.intervention` | `guardrail.outcome`=`BLOCKED`\|`ALLOWED` | ✅ **Fully Compliant**. NeMo Guardrails exporter captures every policy intervention (e.g., jailbreak attempt) with precise attribution. |
| **A.4.2** | **Risk Management** | `consensus.check` | `consensus.decision`=`ESCALATE` | ✅ **Compliant**. Risk escalations are explicitly traced as distinct events. |
| **A.6.3** | **Data Management (Input)** | `genai_span` | `gen_ai.content.prompt` | ⚠️ **Partial**. Prompts are captured, but full input data validity is implicit in Pydantic validation (which logs errors but not successful data structures). |
| **A.9.2** | **System Reliability** | `exception` | `status.code`=`ERROR` | ✅ **Compliant**. Exceptions in governance logic are recorded with full stack traces. |
| **A.7.2** | **Accountability** | `http.server.request` | `enduser.id` | ✅ **Compliant**. User Identity is explicitly tagged on all agent request traces. |

> **Note (Jan 2026):** All governance spans now include explicit `iso.control_id` and `iso.requirement` attributes for direct compliance traceability.

## Detailed Trace Analysis

### 1. Policy Enforcement (`src/governance/client.py`)
Every tool call passes through the `governed_tool` decorator, creating a `governance.check` span.
*   **Audit Value**: Proves that *no action* occurred without a policy check.
*   **Attributes**:
    *   `governance.opa_url`: Verifies which policy engine was queried.
    *   `governance.action`: The exact action attempted (e.g., `execute_trade`).
    *   `governance.decision`: The binary outcome (`ALLOW`/`DENY`).

### 2. Consensus Engine (`src/governance/consensus.py`)
For high-value transactions, the system triggers a `consensus.check`.
*   **Audit Value**: Demonstrates "Human-in-the-loop" equivalent logic (Simulated Role-Based Review).
*   **Attributes**:
    *   `consensus.votes`: The raw votes from the Risk Manager and Compliance Officer agents.
    *   `consensus.reason`: The synthesized reason for rejection or approval.

## Conclusion

The Cybernetic Governance Engine's telemetry implementation meets the transparency and accountability requirements of ISO 42001. All critical decision paths, including internal risk debates and policy enforcement, are immutably recorded with correlated User IDs.
