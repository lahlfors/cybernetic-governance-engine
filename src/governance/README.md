# Governance Logic (Layer 3: Enforcement & Bridge)

This directory contains the "Symbolic Control" layer that bridges Policy to Code and enforces Safety in Real-Time.

## Components

### 1. The Transpiler (`transpiler.py`)
**Role:** Automated Rule Derivation (Phase 3).
*   **Input:** Structured `ProposedUCA` objects from the Risk Analyst.
*   **Process:** Parses `constraint_logic` (variable, operator, threshold).
*   **Output:** Generates Python code strings for NeMo actions.
*   **Supported Logic:**
    *   `check_slippage_risk` (Volume based)
    *   `check_drawdown_limit` (Portfolio based)
    *   `check_data_latency` (Temporal)
    *   `check_atomic_execution` (State based)

### 2. NeMo Actions (`nemo_actions.py`)
**Role:** Real-Time Enforcement (Phase 4).
These functions are called by NeMo Guardrails during the "Hot Path" of execution.
*   **Characteristics:**
    *   **Deterministic:** No LLM calls. Execution < 10ms.
    *   **State Aware:** Checks `audit_trail` for multi-leg trade integrity.
    *   **Temporal:** Checks `time.time()` for data freshness.
    *   **Cryptographic:** Checks `approval_token` signatures (Mock AP2).

### 3. Generated Actions (`generated_actions.py`)
A file strictly managed by the `offline_risk_update.py` script. It contains the "Hot Swapped" rules derived from the latest Risk Discovery cycle. `nemo_actions.py` dynamically imports from here.
