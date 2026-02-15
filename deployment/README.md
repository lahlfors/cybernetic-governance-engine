# Governed Financial Advisor Deployment (GKE)

This directory contains the configuration and scripts to deploy the Financial Advisor agent to **Google Kubernetes Engine (GKE)**.

## Architecture

The system is deployed as a distributed microservices architecture on GKE:

1.  **Gateway Service (`gateway-service`)**:
    *   gRPC service (Port 50051).
    *   Acts as the central router and "Physical Layer" for the agent.
    *   Handles Tool Execution and LLM Routing.
    *   Connects to OPA and NeMo Guardrails.

2.  **Financial Advisor Agent (`governed-financial-advisor`)**:
    *   FastAPI backend (Port 8080).
    *   Hosts the LangGraph control plane and ADK agents.
    *   Connects to the Gateway via internal DNS.

3.  **Inference Services**:
    *   `vllm-fast-service`: Hosted vLLM instance for the "Fast Path" (Control Plane/Format Enforcer).
    *   `vllm-reasoning-service`: (Optional) Hosted vLLM instance for the "Reasoning Plane" (if not using Vertex AI).

4.  **Governance Sidecars/Services**:
    *   `opa-service`: Open Policy Agent server.
    *   `nemo-service`: NeMo Guardrails server.

## Prerequisites

*   Google Cloud Project with billing enabled.
*   `gcloud` CLI installed and authenticated.
*   `kubectl` installed (or installed via script).
*   Permissions to manage GKE, Secret Manager, and Artifact Registry.

## Deployment Script

The `deploy_sw.py` script is the central entry point for deploying the entire Cybernetic Governance Engine stack to GKE.

### Usage

**1. Standard Deployment (GKE)**
This will provision a GKE cluster (if missing), build containers, and deploy all services.

```bash
# Deploy to GKE (Standard with GPU Nodes)
python3 deployment/deploy_sw.py --project-id YOUR_PROJECT_ID --region us-central1
```

**2. Customizing Region/Zone**
```bash
python3 deployment/deploy_sw.py \
    --project-id YOUR_PROJECT_ID \
    --region us-east1 \
    --zone us-east1-c
```

**3. Skipping Build (Fast Redeploy)**
If images are already built and you only modified manifests:
```bash
python3 deployment/deploy_sw.py --project-id YOUR_PROJECT_ID --skip-build
```

### Configuration

Configuration is managed via `deployment/config.yaml` (default settings) and `.env` (secrets/overrides).

**Key Environment Variables:**
*   `MODEL_FAST`: Model ID for the fast path (e.g., `Qwen/Qwen2.5-7B-Instruct`).
*   `MODEL_REASONING`: Model ID for the reasoning path.
*   `HUGGING_FACE_HUB_TOKEN`: Required for vLLM to download gated models.
*   `OPENAI_API_KEY`: Required if using OpenAI models via NeMo.

## Terraform (Infrastructure as Code)

For managing the GKE cluster and underlying VPC via Terraform:

```bash
cd deployment/terraform
terraform init
terraform apply -var="project_id=YOUR_PROJECT_ID"
```

The Terraform state tracks the GKE cluster, Node Pools, and Secret Manager resources. The `deploy_sw.py` script respects existing infrastructure.

## Post-Deployment Verification

### 1. Check Pod Status

```bash
kubectl get pods -n governance-stack
```

Expected output should show `Running` status for:
*   `gateway-service-*`
*   `governed-financial-advisor-*`
*   `vllm-fast-*` (if enabled)
*   `financial-advisor-ui-*`

### 2. Access the UI

The deployment script will output the LoadBalancer IP for the UI. You can also find it via:

```bash
kubectl get service financial-advisor-ui -n governance-stack
```

Open `http://<EXTERNAL-IP>` in your browser.

### 3. Test Backend API

Use `kubectl port-forward` to access the backend locally:

```bash
kubectl port-forward svc/governed-financial-advisor 8080:80 -n governance-stack
```

Then query the agent:
```bash
curl -X POST localhost:8080/agent/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello"}'
```
