# System-Theoretic Process Analysis (STPA) Implementation

## Overview

This document details the STPA analysis applied to the Financial Advisor system (Module 5) and its implementation in code.

---

## 1. System Control Structure

*   **Controller:** Financial AI Agent (Planner/Executor).
*   **Actuators:** Gateway Tools (`execute_trade`, `write_db`).
*   **Controlled Process:** Financial Markets / Banking Ledger.
*   **Sensors:** Market Data Feeds, OPA Policy Engine.

---

## 2. Unsafe Control Actions (UCAs)

| ID | Category | Description | Implementation |
| :--- | :--- | :--- | :--- |
| **UCA-1** | Unsafe Action | Agent executes write operation without approval token. | `STPAValidator` check for `approval_token`. |
| **UCA-2** | Wrong Timing | Agent executes trade with stale market data (>200ms latency). | `STPAValidator` check for `latency_ms`. |
| **UCA-3** | Unsafe Action | Agent outputs PII to user interface. | NeMo Guardrails (`verify_content_safety`). |
| **UCA-4** | Stopped Too Soon | Agent debits account but fails to credit asset (Atomic Failure). | Graph Transaction Logic (Future Work). |
| **UCA-5** | Unsafe Action | Agent executes buy when drawdown > 4.5%. | `SafetyFilter` (CBF) in `SymbolicGovernor`. |

---

## 3. Implementation Details

The STPA constraints are encoded in the **Trading Knowledge Graph** (Ontology).

*   **File:** `src/gateway/governance/ontology.py`
*   **Validator:** `src/gateway/governance/stpa_validator.py`

The Validator is invoked by the **Symbolic Governor** for every action. If a UCA is detected, the action is blocked (or interrupted if running in parallel).
