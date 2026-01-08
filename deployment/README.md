# Governed Financial Advisor Deployment

This directory contains the configuration and scripts to deploy the Financial Advisor agent to Google Cloud Run with a secure Open Policy Agent (OPA) sidecar.

## Architecture

The system is deployed as a **single Cloud Run Service** that follows the multi-container sidecar pattern:

1.  **Ingress Container (Financial Advisor):**
    *   Hosts the **LangGraph** Agent application (`financial_advisor.server:app`).
    *   Exposes the HTTP API on port 8080.
    *   Enforces governance by calling the local OPA sidecar before executing sensitive tools.
    *   Connects to **Cloud Memorystore (Redis)** for state persistence.

2.  **Sidecar Container (Open Policy Agent):**
    *   Runs OPA as a server on `localhost:8181`.
    *   Enforces policies defined in Rego (e.g., `deployment/system_authz.rego`, `deployment/finance_policy.rego`).
    *   Protected by Bearer Token authentication (token shared via Secret Manager).
    *   Pinned to version `0.68.0-static` for stability.

## Prerequisites

*   Google Cloud Project with billing enabled.
*   `gcloud` CLI installed and authenticated.
*   Permissions to manage Cloud Run, Secret Manager, and Artifact Registry/Cloud Build.
*   **Redis (Cloud Memorystore):** Required for persistent memory. The script will auto-provision a Basic Tier instance if configured.
*   **Optional:** [Serverless VPC Access](https://cloud.google.com/run/docs/configuring/vpc-connectors) connector (Required for Redis/Memorystore connectivity).

The `deploy_all.py` script is the central entry point for deploying the entire Cybernetic Governance Engine stack. It orchestrates the provisioning and configuration of:

1.  **Redis**: Provisions or verifies a Redis instance (for persistent state).
2.  **Secrets & Config**: Updates Secret Manager (OPA policies, auth tokens).
3.  **Cloud Run Services**: Builds and deploys the Backend (`governed-financial-advisor`) and UI (`financial-advisor-ui`) services.

### Usage

By default, the script **deploys all services** (Redis, UI, Main Service). Use `--skip-*` flags to opt out.

```bash
# Full deployment (deploys everything)
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID

# Deploy to specific region
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID --region europe-west1

# Skip specific services
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID --skip-build       # Skip container build
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID --skip-ui          # Skip UI deployment
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID --skip-redis       # Skip Redis provisioning

# Use existing resources
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID --redis-host "10.0.0.5"
```

### UI Deployment

The script automatically deploys the Streamlit UI as a separate Cloud Run service (`financial-advisor-ui`).
*   **Build:** Submits `ui/` to Cloud Build.
*   **Configuration:** Automatically injects the `BACKEND_URL` of the deployed backend service.
*   **Access:** The UI is deployed with `--allow-unauthenticated` for easy access.

## Security Features

*   **Identity:** Uses Bearer Token authentication between the App and Sidecar to prevent unauthorized access to the policy engine (Defense in Depth).
*   **Fail-Closed:** The application fails securely if the OPA sidecar is unreachable.
*   **Startup Boost:** Uses Cloud Run CPU Boost to minimize cold start latency.
*   **Startup Dependency:** Uses the `dependsOn` configuration to ensure the application container waits for the OPA sidecar's health check to pass before starting.

## State Management

**Persistent:**
The application uses Redis to persist the LangGraph state. Ensure a VPC connector is configured if using Cloud Memorystore.
