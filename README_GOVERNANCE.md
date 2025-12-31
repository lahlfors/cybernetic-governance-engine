# Cybernetic Governance Implementation

This repository contains the implementation of the Cybernetic Governance framework for the Financial Advisor agent.

## Architecture

The system enforces "Variety Attenuation" through three layers of governance:

1.  **Layer 1 (Syntax):** Pydantic models strictly define tool inputs (`financial_advisor/tools/trades.py`).
2.  **Layer 2 (Policy):** Open Policy Agent (OPA) evaluates Rego policies to block high-risk actions (`financial_advisor/governance.py`).
3.  **Layer 3 (Semantics):** A "Verifier" LLM agent reviews the worker's proposed actions before execution (`financial_advisor/sub_agents/governed_trader/`).

## Local Demonstration (PoC)

To run the standalone proof-of-concept:

1.  Start the OPA server (with production config):
    ```bash
    ./opa run --server --config-file=deployment/opa_config.yaml ./governance_poc/finance_policy.rego
    ```

2.  Run the demo script:
    ```bash
    python3 governance_poc/real_governance_demo.py
    ```

## Cloud Run Deployment (Sidecar Pattern)

This project is designed to run on Google Cloud Run using the multi-container (sidecar) pattern.

### Prerequisites

1.  **Google Cloud Project** with Cloud Run enabled.
2.  **Secret Manager** enabled.

### Deployment Steps

1.  **Create Secrets:**
    Upload the Rego policy and OPA configuration to Secret Manager.
    ```bash
    gcloud secrets create finance-policy-rego --data-file=governance_poc/finance_policy.rego
    gcloud secrets create opa-configuration --data-file=deployment/opa_config.yaml
    ```

2.  **Build the Agent Container:**
    ```bash
    gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/financial-advisor:latest .
    ```

3.  **Deploy the Service:**
    Update `deployment/service.yaml` with your image URL and deploy.
    ```bash
    gcloud beta run services replace deployment/service.yaml
    ```

### Networking

*   **Ingress:** The Agent container listens on port 8080.
*   **Internal:** The Agent communicates with the OPA sidecar via `localhost:8181`.
*   **Isolation:** The OPA container is not exposed to the public internet.
