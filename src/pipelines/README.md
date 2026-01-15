# Vertex AI Governance Pipeline

This directory contains the definitions for the **Green Stack Governance Loop** implemented as a Vertex AI (Kubeflow) Pipeline.

## Pipeline: `green_stack_governance_loop`

**File:** `green_stack_pipeline.py`

This pipeline automates the continuous feedback loop between Risk Discovery and Policy Enforcement.

### Components

1.  **Risk Discovery (`risk_discovery_op`)**
    *   **Input:** Trading Strategy Description.
    *   **Action:** Runs the **Risk Analyst Agent** (A2) offline. It identifies specific financial hazards (Slippage, Drawdown, etc.) relevant to the current market regime.
    *   **Output:** A list of structured `ProposedUCA` objects (JSON).

2.  **Policy Transpilation (`policy_transpilation_op`)**
    *   **Input:** UCAs from the Discovery step.
    *   **Action:** Runs the **Policy Transpiler**. It converts the abstract UCA constraints (e.g., `slippage > 1%`) into executable Python code strings.
    *   **Output:** Generated Python module content.

3.  **Rule Deployment (`rule_deployment_op`)**
    *   **Input:** Generated Code.
    *   **Action:** Deploys the new rules to the runtime environment (Simulated update to `generated_actions.py`).

## Running the Pipeline

To compile the pipeline:
```bash
python src/pipelines/green_stack_pipeline.py
```
This produces `green_stack_pipeline.json` (KFP v2 Spec) which can be uploaded to Vertex AI Pipelines.

## Production Note
The components use `packages_to_install` to ensure the `google-adk` and project dependencies are available in the container.
