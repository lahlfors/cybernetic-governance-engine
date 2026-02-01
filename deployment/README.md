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

2.  **Financial Advisor Agent (HTTP / Vertex AI)**
    *   **Service Name:** `governed-financial-advisor` (GKE) OR `Vertex AI Agent`
    *   **Role:** The core agent logic. Can run as a container on GKE or as a managed Reasoning Engine on Vertex AI.
    *   **Source:** `src/governed_financial_advisor`

3.  **NeMo Guardrails Service (HTTP)**
    *   **Service Name:** `nemo-guardrails`
    *   **Role:** Dedicated sidecar/service for semantic safety checks.
    *   **Source:** `src/governed_financial_advisor/governance/nemo_server.py`

## Deployment

### 1. Full Stack Deployment (Recommended)

Terraform is the master orchestrator. It creates the infrastructure and triggers the application deployment automatically.

```bash
cd deployment/terraform

# Initialize Terraform (First time only)
terraform init

# Plan and Apply
# This provisions GKE, Redis, Network, Secrets, and Deploys the App.
terraform apply -var="project_id=YOUR_PROJECT_ID"
```

### 2. Software-Only Updates

If the infrastructure is already running:

```bash
# Run from the repository root
python3 deployment/deploy_sw.py \
  --project-id YOUR_PROJECT_ID \
  --tf-managed \
  --redis-host REDIS_IP \
  --cluster-name governance-cluster
```

### 3. Hybrid Deployment (Vertex AI Agent Engine)

To deploy the Agent to **Vertex AI Agent Engine** instead of GKE:

```bash
python3 deployment/deploy_sw.py \
  --project-id YOUR_PROJECT_ID \
  --tf-managed \
  --redis-host REDIS_IP \
  --cluster-name governance-cluster \
  --deploy-agent-engine
```

**Architecture:**
*   **Agent:** Deployed to Vertex AI Agent Engine.
*   **Gateway:** Deployed to Cloud Run (connects to GKE).
*   **Inference:** Remains on GKE (vLLM).

**Prerequisites:**
Ensure Terraform has been applied to create the necessary Service Accounts (`agent-engine-sa`, `gateway-sa`) and Buckets (`-agent-artifacts`).

## Architecture & Security Details

### GKE (Backend & Inference)
*   **vLLM:** Runs as a dedicated Deployment on GPU nodes (NVIDIA L4).
*   **Backend (Advisor):** Runs as a Deployment (if not using Vertex AI).
*   **OPA Sidecar:** The backend pod includes an Open Policy Agent (OPA) sidecar.

### Cloud Run (UI & Gateway)
*   **Gateway:** Serves as the gRPC entry point.
*   **UI:** Connects to the Gateway/Backend.

### Identity & Access
*   **Workload Identity:** GKE workloads use Kubernetes Service Accounts mapped to Google Service Accounts (GSA).

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

