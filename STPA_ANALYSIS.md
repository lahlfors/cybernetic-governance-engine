# STPA Analysis: Financial Advisor Agent
## 1. System Control Structure

### Controllers
*   **Financial Coordinator (Supervisor):** High-level intent routing.
*   **Worker Agent (System 1):** Proposes trading strategies and actions.
*   **Verifier Agent (System 3):** Audits proposed actions for semantic safety.
*   **OPA Policy Engine (Layer 2):** Deterministic policy enforcement.

### Actuators (Tools)
*   `execute_trade`: Commits financial transactions.
*   `route_request`: Transitions state between agents.

### Controlled Process
*   **Financial Market / Exchange:** The external environment where trades are executed.
*   **User Session:** The state of the user's financial portfolio.

### Feedback Loops
*   **Tool Outputs:** Success/Failure messages from `execute_trade`.
*   **Risk Packets:** Structured feedback from `verifier_agent`.
*   **Telemetry:** OpenTelemetry traces for observability.

---

## 2. Unsafe Control Actions (UCAs)

| ID | Control Action | Unsafe Context | Hazard |
|----|---------------|----------------|--------|
| **UCA-1** | `execute_trade` | Trade amount exceeds risk threshold ($10k) and no Consensus check is performed. | Financial Loss / Unauthorized High-Value Transaction |
| **UCA-2** | `execute_trade` | Trade involves a restricted symbol (e.g., 'BLOCKED') defined in Policy. | Regulatory Violation |
| **UCA-3** | `execute_trade` | Agent hallucinates valid UUID/Symbol that does not exist in reality. | System Error / Vaporwork |
| **UCA-4** | `route_request` | Router sends `TRADING_STRATEGY` intent to `data_analyst` instead of `governed_trader`. | Process Failure / Context Loss |
| **UCA-5** | `verifier_agent` | Verifier approves a trade based on flawed reasoning (Deception/Hallucination) without CoT check. | Semantic Verification Failure |

---

## 3. Gap Analysis & Refactoring Strategy

### VSM & Risk Stack Mapping

| Layer / System | Current Status | Identified Gap | Remediation Strategy |
|----------------|----------------|----------------|----------------------|
| **System 1 (Ops)** | `worker_agent` exists. | Lacks robust output typing (relying on tool call). | Enforce Pydantic validation (Layer 1). |
| **System 2 (Coord)** | `financial_coordinator` exists. | Good. Uses HD-MDP routing. | Maintain `route_request` strictness. |
| **System 3 (Control)** | `verifier_agent` exists. | Output is unstructured text/json string. No schema enforcement. | **Refactor:** Enforce `RiskPacket` schema. |
| **System 4 (Intel)** | `risk_analyst` exists. | Reactive, not predictive. No "World Model" simulation. | **Future:** Implement JEPA-style simulation. |
| **System 5 (Policy)** | `OPAClient` exists. | Good. Maps to Layer 2. | Maintain OPA integration. |
| **Layer 4 (Consensus)** | **MISSING** | High-stakes decisions rely on single model inference. | **Implement:** `ConsensusEngine` for >$10k trades. |
| **Observability** | Basic OTel. | Lacks GenAI Semantic Conventions (Prompt/CoT/Tokens). | **Refactor:** Update `telemetry.py` with GenAI spans. |

## 4. Implementation Plan

1.  **Layer 3 Hardening:** Update `verifier_agent` to strictly output `RiskPacket`.
2.  **Observability:** Instrument `telemetry.py` with `gen_ai.*` attributes.
3.  **Layer 4 Consensus:** Implement `ConsensusEngine` to mitigate UCA-1.
