# Governed Financial Advisor Deployment

This directory contains the configuration and scripts to deploy the Financial Advisor agent using the **Agentic Gateway Pattern**.

## Architecture

The system is deployed as a **Triple-Hybrid Architecture** consisting of three distinct services:

1.  **Agentic Gateway (gRPC)**
    *   **Service Name:** `gateway`
    *   **Language:** Python (gRPC + LangGraph)
    *   **Role:** The single entry point for all client traffic. Handles request orchestration, tool execution, and policy enforcement (OPA).
    *   **Source:** `src/gateway`
    *   **Port:** 8080 (Cloud Run) / 50051 (gRPC default)

2.  **Financial Advisor Agent (HTTP)**
    *   **Service Name:** `governed-financial-advisor` (or `advisor`)
    *   **Language:** Python (FastAPI + LangChain)
    *   **Role:** Hosts the core agent logic and sub-agents (`data_analyst`, `risk_analyst`, etc.).
    *   **Source:** `src/governed_financial_advisor`
    *   **Port:** 8080

3.  **NeMo Guardrails Service (HTTP)**
    *   **Service Name:** `nemo-guardrails` (or `nemo`)
    *   **Language:** Python (FastAPI + NeMo Guardrails)
    *   **Role:** Dedicated sidecar/service for semantic safety checks (jailbreak detection, hallucination checks) and input/output validation.
    *   **Source:** `src/governed_financial_advisor/governance/nemo_server.py`
    *   **Port:** 8000

## Deployment

Deployment is managed via **Terraform** ensuring reproducible infrastructure and state management.

```bash
cd terraform
# Initialize Terraform
terraform init

# Apply Configuration
terraform apply
```

### Script Usage
*   `deploy_sw.py`: A helper script invoked by Terraform (or manually if needed) to handle the application deployment logic (Kubernetes manifests, Helm charts, etc.) on top of the provisioned infrastructure.

### Components Built
*   `gateway`: Built from `src/gateway/Dockerfile`
*   `advisor`: Built from `Dockerfile`
*   `nemo`: Built from `Dockerfile.nemo`

## Prerequisites

*   Google Cloud Project with billing enabled.
*   `gcloud` CLI installed and authenticated.
*   `terraform` and `kubectl` installed.
*   Permissions to manage Cloud Run, Artifact Registry, and GKE.

## Service Inter-Communication

*   **Gateway -> OPA**: The Gateway makes gRPC/HTTP calls to OPA for policy decisions.
*   **Gateway -> NeMo**: The Gateway calls the NeMo service for content safety checks.
*   **Gateway -> Advisor**: The Gateway routes user queries to the Advisor agent.

## Verification

### Check Service Health

```bash
# Check Gateway
gcloud run services describe gateway --region us-central1 --format 'value(status.url)'

# Check NeMo
gcloud run services describe nemo --region us-central1 --format 'value(status.url)'
```

### View Logs

```bash
gcloud logging read 'resource.labels.service_name="gateway"' --limit 20
```

