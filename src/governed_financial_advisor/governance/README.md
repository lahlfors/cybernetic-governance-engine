# Governance Logic (Layer 3: Enforcement & Bridge)

This directory contains the "Symbolic Control" layer that bridges Policy to Code and enforces Safety in Real-Time.

## Architecture Refactor: Offline Governance Pipeline

The governance architecture has been refactored to decouple policy generation (System 2) from runtime enforcement (System 1).

### 1. Offline Pipeline (Vertex AI + Cloud Run)
Instead of real-time transpilation, policy updates are handled by an offline pipeline orchestrated by Kubeflow Pipelines (KFP).

*   **Trigger:** Eventarc detects new STAMP specifications (`.yaml`) in the GCS Policy Registry.
*   **Execution:** A Cloud Run Job (`scripts/run_transpiler_job.py`) is triggered.
*   **Logic:**
    1.  **PolicyLoader:** Fetches the STAMP spec from GCS.
    2.  **Transpiler:** Converts STAMP hazards into OPA Rego and NeMo Python actions.
    3.  **Judge Agent:** An LLM-based verifier back-translates the Rego code to Natural Language to ensure it matches the original STAMP intent. **Updates are rejected if verification fails.**
    4.  **Deployment:** Verified policies are bundled (`.tar.gz`) and uploaded to the GCS Policy Registry.

### 2. The Transpiler (`transpiler.py`)
**Role:** Automated Rule Derivation (Phase 3).
*   **Input:** Structured `ProposedUCA` objects from the Risk Analyst.
*   **Process:** Parses `constraint_logic` (variable, operator, threshold).
*   **Verification:** Invokes `JudgeAgent` to verify semantic alignment.
*   **Output:** Generates Python code strings for NeMo actions and Rego policies.

### 3. NeMo Actions (`nemo_actions.py`)
**Role:** Real-Time Enforcement (Phase 4).
These functions are called by NeMo Guardrails (running **In-Process**) during the "Hot Path" of execution. They implement a **Hybrid Policy** model:

*   **Static Mechanism (CBF):** Critical safety checks like **Drawdown Limit** are hardcoded as **Control Barrier Functions** ($h(x) = Limit - Value$). This ensures mathematical rigor and prevents AI hallucinations from altering the safety logic itself.
*   **Dynamic Policy (Configuration):** While the *logic* is static, the *parameters* are read dynamically.

### 4. Policy Registry (GCS)
Policies are no longer hardcoded in `agent.py`. The **Risk Analyst Agent** uses `PolicyLoader` to fetch the latest hazards from the GCS bucket at startup, ensuring the agent's reasoning is always synchronized with the latest safety case.

## Files

*   `transpiler.py`: Core logic for STAMP -> Code conversion.
*   `judge.py`: The "Judge Agent" verification logic.
*   `policy_loader.py`: Client for fetching specs/bundles from GCS.
*   `pipeline_components.py`: KFP component definitions for the offline pipeline.
*   `nemo_actions.py`: Runtime safety checks.
