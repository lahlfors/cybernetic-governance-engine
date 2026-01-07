# Governed Financial Advisor Deployment

This directory contains the configuration and scripts to deploy the Financial Advisor agent to Google Cloud Run with a secure Open Policy Agent (OPA) sidecar.

## Architecture

The system is deployed as a **single Cloud Run Service** that follows the multi-container sidecar pattern:

1.  **Ingress Container (Financial Advisor):**
    *   Hosts the monolithic Agent application (`financial_advisor.agent.root_agent`).
    *   Includes the root `financial_coordinator` and all sub-agents (`data_analyst`, `execution_analyst`, `governed_trader`, `risk_analyst`) running in the same process.
    *   Exposes the HTTP API on port 8080.
    *   Enforces governance by calling the local OPA sidecar before executing sensitive tools.

2.  **Sidecar Container (Open Policy Agent):**
    *   Runs OPA as a server on `localhost:8181`.
    *   Enforces policies defined in Rego (e.g., `deployment/system_authz.rego`, `deployment/finance_policy.rego`).
    *   Protected by Bearer Token authentication (token shared via Secret Manager).
    *   Pinned to version `0.68.0-static` for stability.

## Prerequisites

*   Google Cloud Project with billing enabled.
*   `gcloud` CLI installed and authenticated.
*   Permissions to manage Cloud Run, Secret Manager, and Artifact Registry/Cloud Build.

## Deployment

The `deploy_cloud_run.py` script automates the entire process:
1.  Creates/Updates necessary Secrets (`opa-auth-token`, policies, config).
2.  Builds the application container image using Cloud Build.
3.  Deploys the multi-container service to Cloud Run.

### Usage

```bash
# Deploy to default region (us-central1)
python3 deployment/deploy_cloud_run.py --project-id YOUR_PROJECT_ID

# Deploy to specific region
python3 deployment/deploy_cloud_run.py --project-id YOUR_PROJECT_ID --region europe-west1

# Skip image build (re-deploy configuration only)
python3 deployment/deploy_cloud_run.py --project-id YOUR_PROJECT_ID --skip-build
```

## Security Features

*   **Identity:** Uses Bearer Token authentication between the App and Sidecar to prevent unauthorized access to the policy engine (Defense in Depth).
*   **Fail-Closed:** The application fails securely if the OPA sidecar is unreachable.
*   **Startup Boost:** Uses Cloud Run CPU Boost to minimize cold start latency, ensuring the sidecar is ready before the app serves traffic.
*   **Startup Dependency:** Uses the `dependsOn` configuration to ensure the application container waits for the OPA sidecar's health check to pass before starting, preventing startup race conditions.
