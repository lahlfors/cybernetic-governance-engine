# Cybernetic Governance Engine - Deployment

This directory contains the Infrastructure-as-Code (Terraform) and deployment scripts to provision the Cybernetic Governance Engine.

## Architecture

The system uses a **Hybrid Cloud Architecture** on Google Cloud Platform:

1.  **Infrastructure (Terraform Managed)**
    *   **GKE Cluster (Private):** Hosts the Backend (`governed-financial-advisor`) and Inference Engine (`vLLM` on NVIDIA L4 GPUs).
        *   **Security:** Shielded Nodes, Binary Authorization ready, Workload Identity.
        *   **Networking:** Private Nodes, Cloud NAT/Router for egress.
    *   **Cloud Memorystore (Redis):** Managed Redis instance for persistent session state and checkpointer.
    *   **Secret Manager:** Stores API keys (OpenAI, Gemini), OPA policies, and configuration secrets.
    *   **Cloud Run (UI):** Hosts the Streamlit UI, effectively verifying the "external client" path.

2.  **Application (Python Script Managed)**
    *   **Deployment Orchestration:** `deploy_sw.py` acts as the glue code, triggered by Terraform (or run manually) to build containers and apply Kubernetes manifests.

## Prerequisites

*   [Terraform](https://developer.hashicorp.com/terraform/install) (v1.0+)
*   [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`gcloud`)
*   `kubectl` (installed via `gcloud components install kubectl`)
*   Python 3.11+

## Deployment Guide

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

If the infrastructure is already running and you only need to deploy code changes (Backend/UI/vLLM):

```bash
# Run from the repository root
python3 deployment/deploy_sw.py \
  --project-id YOUR_PROJECT_ID \
  --tf-managed \
  --redis-host REDIS_IP \
  --cluster-name governance-cluster
```

*   `--tf-managed`: Skips infrastructure provisioning (Redis creation, API enablement) since Terraform owns it.

## Architecture & Security Details

### GKE (Backend & Inference)
*   **vLLM:** Runs as a dedicated Deployment on GPU nodes (NVIDIA L4).
*   **Backend:** Runs as a Deployment. Connects to vLLM via internal K8s Service (`vllm-inference`).
*   **OPA Sidecar:** The backend pod includes an Open Policy Agent (OPA) sidecar for local, low-latency policy enforcement.

### Cloud Run (UI)
*   Deploys `financial-advisor-ui`.
*   Connects to the Backend via the GKE Load Balancer IP.
*   Accessible securely via HTTPS.

### Identity & Access
*   **Workload Identity:** GKE workloads use Kubernetes Service Accounts mapped to Google Service Accounts (GSA) to access Vertex AI and Secret Manager. No long-lived service account keys are stored in the cluster.

## Verification

After deployment, `terraform output` or the script will provide the Backend IP and UI URL.

### Health Check

```bash
# Backend Health
curl http://<BACKEND_LOAD_BALANCER_IP>/health

# vLLM Status (Internal check from backend pod)
kubectl exec -it -n governance-stack <BACKEND_POD> -- curl http://vllm-inference:8000/health
```

### Observability
*   **Logs:** All logs are streamed to Cloud Logging.
*   **Tracing:** Langfuse tracing is enabled if configured in Secret Manager/Env.
