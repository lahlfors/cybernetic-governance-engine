# Governed Financial Advisor - Deployment Guide

This guide describes the recommended "Enterprise" deployment strategy using **Terraform** as the single source of truth for infrastructure and **Vertex AI Reasoning Engine** for the agent runtime.

## Analysis: Terraform vs. `deploy_all.py`

### Why Terraform is More Effective
*   **State Management**: Terraform maintains a state file (`terraform.tfstate`), allowing it to track created resources, detect drift, and safely destroy or update specific components without manual intervention. `deploy_all.py` is imperative and stateless; re-running it often attempts to recreate resources or fails if they already exist unless extensive checks are written.
*   **Declarative Infrastructure**: HCL (Terraform's language) describes *what* the infrastructure should look like, not *how* to build it step-by-step. This reduces bugs in complex dependency graphs.
*   **Standardization**: Terraform is the industry standard for cloud infrastructure. It integrates with Policy-as-Code (Sentinel), CI/CD pipelines, and security scanners better than custom Python scripts.
*   **Separation of Concerns**: `deploy_all.py` mixed Python application logic (pickling agents) with infrastructure calls (`gcloud`). The new approach separates these:
    *   **Terraform**: Manages Google Cloud resources (Cloud Run, Vertex AI, Firestore, Secrets).
    *   **Build Scripts**: (`scripts/prepare_agent.py`) Handle artifact preparation, invoked by Terraform only when needed.

### The Hybrid "Effective" Strategy
While Terraform is superior for infrastructure, it cannot natively serialize Python objects (pickle) or package dependencies. Therefore, the **most effective strategy** is a **Terraform-driven** approach that invokes specialized build scripts via `local-exec` provisioners. This keeps Terraform as the master orchestrator while leveraging Python for code-specific tasks.

## Architecture

1.  **Agent Logic**: Deployed to **Vertex AI Reasoning Engine** (Serverless, Managed).
2.  **Governance**:
    *   **NeMo Guardrails**: Standalone Cloud Run Service.
    *   **OPA (Open Policy Agent)**: Standalone Cloud Run Service.
3.  **Persistence**: **Firestore** (Native Mode) replaces Redis.
4.  **Gateway & UI**:
    *   **Backend (Gateway)**: Cloud Run service (`src/server.py`) that proxies requests to the Reasoning Engine and enforces NeMo checks.
    *   **Frontend**: Cloud Run service (`ui/`) serving the web interface.

## Deployment Instructions

### Prerequisites
*   Google Cloud Project
*   `gcloud` CLI authenticated
*   Terraform >= 1.0
*   Python 3.10+

### Steps

1.  **Initialize Terraform**:
    ```bash
    cd terraform
    terraform init
    ```

2.  **Configure Variables**:
    Create a `terraform.tfvars` file or use environment variables:
    ```bash
    export TF_VAR_project_id="your-project-id"
    export TF_VAR_region="us-central1"
    export TF_VAR_opa_auth_token="your-secure-token"
    ```

3.  **Deploy**:
    ```bash
    terraform apply
    ```
    *Terraform will automatically run `scripts/prepare_agent.py` to package the agent code.*

4.  **Access the Application**:
    Terraform will output the `ui_url`. Open this URL in your browser.

## Migration from `deploy_all.py`
The `deploy_all.py` script has been **removed**. All deployments are now handled via Terraform. If you need to teardown resources created by the old script, run:
```bash
python3 deployment/teardown.py
```
Then proceed with the Terraform deployment.
