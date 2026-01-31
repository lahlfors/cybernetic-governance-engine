<<<<<<< HEAD
# Governed Financial Advisor Deployment

This directory contains the configuration and scripts to deploy the Financial Advisor agent to Google Cloud Run with a secure Open Policy Agent (OPA) sidecar.

## Architecture

The system is deployed as a **single Cloud Run Service** that follows the multi-container sidecar pattern:

1.  **Ingress Container (Financial Advisor):**
    *   Hosts the monolithic Agent application (`src.agents.financial_advisor.agent.root_agent`).
    *   Includes the root `financial_coordinator` and all sub-agents (`data_analyst`, `execution_analyst`, `governed_trader`, `risk_analyst`) running in the same process.
    *   Exposes the HTTP API on port 8080.
    *   Enforces governance by calling the local OPA sidecar before executing sensitive tools.

2.  **Sidecar Container (Open Policy Agent):**
    *   Runs OPA as a server on `localhost:8181`.
    *   Enforces policies defined in Rego (e.g., `deployment/system_authz.rego`, `src/governance/policy/finance_policy.rego`).
    *   Protected by Bearer Token authentication (token shared via Secret Manager).
    *   Pinned to version `0.68.0-static` for stability.

## Prerequisites

*   Google Cloud Project with billing enabled.
*   `gcloud` CLI installed and authenticated.
*   Permissions to manage Cloud Run, Secret Manager, and Artifact Registry/Cloud Build.
*   **Optional:** [Serverless VPC Access](https://cloud.google.com/run/docs/configuring/vpc-connectors) connector (Required for Redis/Memorystore connectivity).

## Deployment Script

The `deploy_all.py` script is the central entry point for deploying the entire Cybernetic Governance Engine stack. It orchestrates the provisioning and configuration of:

1.  **Redis**: Provisions or verifies a Redis instance (for session state persistence).
2.  **Secrets & Config**: Updates Secret Manager (OPA policies, auth tokens).
3.  **Cloud Run Services**: Builds and deploys the Backend (`governed-financial-advisor`) and UI (`financial-advisor-ui`) services.

### Usage

The deployment script enforces "Golden Path" configurations to ensure reliability and performance. Ad-hoc model configuration (e.g., custom quantization) is disabled.

**Supported Configurations:**

| Family | Default Model | Accelerator | Optimization |
| :--- | :--- | :--- | :--- |
| **Llama** | `meta-llama/Llama-3.1-8B-Instruct` | **GPU** (T4, L4, A100) | `gptq`, `float16` |
| **Gemma** | `google/gemma-3-27b-it` | **GPU** (L4, A100) | `bfloat16` (Text Only) |
| **Gemma** | `google/gemma-3-27b-it` | **TPU** (v5e) | `bfloat16` |

> **Note:** Gemma models are **blocked** on T4 GPUs due to lack of native bfloat16 support.

```bash
# 1. Llama 3.1 8B (Default Golden Path)
# Target: NVIDIA T4 (Low Cost)
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID

# 2. Gemma 3 27B on GPU
# Target: NVIDIA L4 or A100 (Required for bfloat16)
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID \
    --model-family gemma \
    --accelerator-type l4  # or a100

# 3. Gemma 3 27B on TPU
# Target: TPU v5e
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID \
    --model-family gemma \
    --accelerator tpu \
    --zone us-east1-c

# 4. Custom Model ID (Must match Family Golden Path)
# Example: Deploying a fine-tuned Llama 8B
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID \
    --model-family llama \
    --model-id "my-org/my-finetuned-llama-8b"

# Skip specific services
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID --skip-build  # Skip container build
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID --skip-ui     # Skip UI deployment
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID --skip-redis  # Skip Redis provisioning

# Use existing Redis
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID --redis-host "10.0.0.5"
```

### UI Deployment

The script automatically deploys the Streamlit UI as a separate Cloud Run service (`financial-advisor-ui`).
*   **Build:** Submits `ui/` to Cloud Build.
*   **Configuration:** Automatically injects the `BACKEND_URL` of the deployed backend service.
*   **Access:** The UI is deployed with `--allow-unauthenticated` for easy access (since it handles its own auth headers to the backend).

## Security Features

*   **Identity:** Uses Bearer Token authentication between the App and Sidecar to prevent unauthorized access to the policy engine (Defense in Depth).
*   **Fail-Closed:** The application fails securely if the OPA sidecar is unreachable.
*   **Startup Boost:** Uses Cloud Run CPU Boost to minimize cold start latency, ensuring the sidecar is ready before the app serves traffic.
*   **Startup Dependency:** Uses the `dependsOn` configuration to ensure the application container waits for the OPA sidecar's health check to pass before starting, preventing startup race conditions.

## Redis Connectivity

For session state persistence, Cloud Run requires a **Serverless VPC Access connector** to reach Cloud Memorystore (Redis).

If a VPC connector is not configured:
*   The application will timeout connecting to Redis
*   The system will fallback to **Ephemeral Mode** (in-memory state only)
*   Session state will NOT persist across container restarts

To configure VPC connectivity:
1.  Create a [Serverless VPC Access connector](https://cloud.google.com/run/docs/configuring/vpc-connectors)
2.  Add `--vpc-connector YOUR_CONNECTOR` to the Cloud Run deploy command

## Post-Deployment Verification

### 1. Check Service Health

```bash
# Get service URL
gcloud run services describe governed-financial-advisor \
  --project YOUR_PROJECT_ID \
  --region us-central1 \
  --format "value(status.url)"
```

### 2. Access Services (Authenticated Deployments)

If your services are not publicly accessible, use **Cloud Run Proxy** to tunnel requests:

```bash
# Terminal 1: Backend proxy
gcloud run services proxy governed-financial-advisor \
  --project YOUR_PROJECT_ID \
  --region us-central1 \
  --port 8081

# Terminal 2: UI proxy  
gcloud run services proxy financial-advisor-ui \
  --project YOUR_PROJECT_ID \
  --region us-central1 \
  --port 8080
```

Then open `http://localhost:8080` in your browser.

### 3. Test Backend API

```bash
# Health check
curl localhost:8081/health

# Query the agent
curl -X POST localhost:8081/agent/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello"}'
```

### 4. View Logs

```bash
gcloud logging read 'resource.type="cloud_run_revision"' \
  --project YOUR_PROJECT_ID \
  --limit 50 \
  --format "value(textPayload)"
```

=======
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
>>>>>>> origin/docs/agentic-gateway-analysis-15132879769016669359
