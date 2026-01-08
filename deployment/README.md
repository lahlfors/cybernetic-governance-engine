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
*   permissions to manage Cloud Run, Secret Manager, and Artifact Registry/Cloud Build.
*   **Vertex AI Agent Engine (ReasoningEngine):** Required for persistent memory. The script will auto-detect existing engines. To verify or create manually:
    ```bash
    # Verify existing engines:
    gcloud asset search-all-resources \
      --scope=projects/YOUR_PROJECT_ID \
      --asset-types='aiplatform.googleapis.com/ReasoningEngine' \
      --format="table(name,assetType,location)"
    
    # Create new engine via ADK CLI:
    adk deploy cloud_run --project=YOUR_PROJECT_ID --region=us-central1
    ```
*   **Optional:** [Serverless VPC Access](https://cloud.google.com/run/docs/configuring/vpc-connectors) connector (Required for Redis/Memorystore connectivity).

The `deploy_all.py` script is the central entry point for deploying the entire Cybernetic Governance Engine stack. It orchestrates the provisioning and configuration of:

1.  **Vertex AI Agent Engine**: Deploys the reasoning engine using `adk deploy agent_engine` (auto-detects staging bucket from `.env`).
2.  **Redis**: Provisions or verifies a Redis instance (for persistent memory).
3.  **Secrets & Config**: Updates Secret Manager (OPA policies, auth tokens).
4.  **Cloud Run Services**: Builds and deploys the Backend (`governed-financial-advisor`) and UI (`financial-advisor-ui`) services.

### Usage

By default, the script **deploys all services** (Agent Engine, Redis, UI, Main Service). Use `--skip-*` flags to opt out.

```bash
# Full deployment (deploys everything)
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID

# Deploy to specific region
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID --region europe-west1

# Skip specific services
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID --skip-build       # Skip container build
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID --skip-ui          # Skip UI deployment
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID --skip-redis       # Skip Redis provisioning
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID --skip-agent-deploy # Skip Agent Engine deploy

# Use existing resources (skips auto-deployment for that resource)
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID --agent-engine-id "your-engine-id"
python3 deployment/deploy_all.py --project-id YOUR_PROJECT_ID --redis-host "10.0.0.5"
```

### Agent Engine Auto-Deployment

The script automatically manages Agent Engine (ReasoningEngine) lifecycle:

1. **Detection**: Uses `gcloud asset search-all-resources` to find existing ReasoningEngines
2. **Auto-Deploy**: Deploys new engine using `adk deploy cloud_run` (default behavior)
3. **Skip Deploy**: Use `--skip-agent-deploy` to skip deployment (use with `--agent-engine-id` for existing engine)

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

## Post-Deployment Configuration

**Automated:**
The deployment script automatically provisions the Vertex AI Agent Engine. No manual configuration is required.


*Without this step, the memory agent will act as a generic chatbot rather than a structured financial profiler.*
