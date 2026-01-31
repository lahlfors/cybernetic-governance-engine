# Governed Financial Advisor - Terraform Deployment

This directory contains the Terraform configuration to deploy the Governed Financial Advisor to Google Cloud, utilizing **Vertex AI Reasoning Engine** for the agent and **Cloud Run** for governance services (NeMo, OPA).

## Architecture

*   **Agent**: Deployed to Vertex AI Reasoning Engine (Serverless).
*   **NeMo Guardrails**: Deployed as a standalone Cloud Run service.
*   **OPA (Open Policy Agent)**: Deployed as a standalone Cloud Run service.
*   **Artifacts**: GCS bucket stores the pickled agent and dependencies.

## Prerequisites

1.  Google Cloud Project with billing enabled.
2.  Terraform installed (>= 1.0).
3.  Python 3.10+ installed.
4.  `gcloud` CLI installed and authenticated.

## Deployment Steps

1.  **Initialize Terraform**:
    ```bash
    cd terraform
    terraform init
    ```

2.  **Plan Deployment**:
    Create a `terraform.tfvars` file or pass variables via command line.
    ```bash
    export TF_VAR_project_id="your-project-id"
    export TF_VAR_opa_auth_token="your-secure-token"
    terraform plan -out=tfplan
    ```

3.  **Apply Deployment**:
    ```bash
    terraform apply tfplan
    ```

    *Note*: During the apply phase, Terraform will automatically run `scripts/prepare_agent.py` via a `local-exec` provisioner. This script pickles the agent with the correct NeMo and OPA URLs (which are generated during the deployment of those services).

## What happens under the hood?

1.  Terraform enables necessary APIs.
2.  Deploys OPA and NeMo to Cloud Run.
3.  Calculates the URLs of these services.
4.  Runs `scripts/prepare_agent.py` with these URLs.
    *   Generates `config/runtime_config.py`.
    *   Pickles the agent.
    *   Packages `src/` and `config/` into `dependencies.tar.gz`.
5.  Uploads artifacts to GCS.
6.  Deploys the Reasoning Engine.

## Outputs

After deployment, Terraform will output:
*   `agent_engine_id`: The ID of the deployed Reasoning Engine.
*   `nemo_url`: The URL of the NeMo Guardrails service.
*   `opa_url`: The URL of the OPA service.
