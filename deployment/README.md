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

By default, the script **deploys all services** (Redis, UI, Main Service). Use `--skip-*` flags to opt out.

```bash
# Full deployment (default: T4 GPU, Regional)
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID

# Deploy optimized for A100 (Spot Instance, Single Zone)
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID \
    --accelerator-type a100 \
    --spot \
    --zone us-central1-f

# Deploy on TPU v5e (Zonal)
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID \
    --accelerator tpu \
    --zone us-east1-c

# Deploy Gemma 27B on H100 (Default: Llama 3 8B)
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID \
    --model-family gemma \
    --accelerator-type a100

# Deploy Custom Model ID
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID \
    --model-id "google/gemma-3-1b-it" \
    --model-family gemma

# Deploy to specific region
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID --region europe-west1

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

