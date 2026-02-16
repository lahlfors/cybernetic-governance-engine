# Financial Advisor (Cybernetic Governance Edition)

**This repository implements the [Cybernetic Governance Framework](README_GOVERNANCE.md), transforming a probabilistic LLM agent into a deterministic, engineering-controlled system.**

## Overview

The Financial Advisor is a multi-agent system designed to assist human financial advisors. Unlike standard "tool-use" agents that can unpredictably call functions, this system uses a **Hybrid Reasoning Architecture** combining deterministic workflow control with LLM-powered reasoning, guided by **Systems-Theoretic Process Analysis (STPA)** to guarantee safety constraints.

Use this authentic reference implementation to understand how to build **high-reliability agentic systems** for regulated industries.

## Architecture: Cloud Run + Vertex AI

This implementation uses a serverless architecture designed for scale and security:

*   **Agent (Reasoning Engine):** Deployed on **Vertex AI Reasoning Engine** (LangChain on Vertex).
*   **Gateway (Control Plane):** Deployed on **Cloud Run** as a consolidated service.
    *   **Orchestrator:** Handles tool execution and routing.
    *   **Governance (NeMo):** Runs in-process within the Gateway to enforce PII masking and safety rails with <10ms latency.
    *   **Policy (OPA):** Runs as a sidecar or internal check for RBAC and business logic.
*   **LLM Backend:** Uses **Google Vertex AI (Gemini)** exclusively for both the Agent and the Governance checks.

### Consolidated Governance

The Gateway Service (`src/gateway`) now includes the **NeMo Guardrails** logic internally, removing the need for a separate NeMo microservice. This reduces latency and simplifies operations.

**Key Features:**
*   **PII Masking:** Automatically detects and masks sensitive data (Email, Phone, SSN) using `Presidio` and `Spacy` (`en_core_web_sm`) before it reaches the LLM or leaves the system.
*   **Jailbreak Detection:** deterministic checks against adversarial inputs.
*   **Policy Enforcement:** OPA policies are evaluated for every tool call.

## Quick Start

### 1. Prerequisites

*   [uv](https://github.com/astral-sh/uv) (for Python dependency management)
*   [Docker](https://docs.docker.com/get-docker/)
*   [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/lahlfors/cybernetic-governance-engine.git
cd cybernetic-governance-engine

# Install dependencies (including NeMo, Presidio, Spacy)
uv sync
```

### 3. Local Development

You can run the Gateway locally with the embedded NeMo Guardrails:

```bash
# Set up environment variables
cp .env.example .env

# Run the Gateway Server
uv run python src/gateway/server/main.py
```

The server will start on `http://localhost:8080`.

### 4. Cloud Deployment

Deploy the entire stack to Google Cloud (Cloud Run + Vertex AI) using the helper script:

```bash
# Ensure you are logged in
gcloud auth login
gcloud config set project <YOUR_PROJECT_ID>

# Deploy
python deployment/deploy_sw.py --project-id <YOUR_PROJECT_ID> --region us-central1
```

This script will:
1.  Build and deploy the **Gateway Service** (with NeMo) to Cloud Run.
2.  Deploy the **OPA Service** (if needed) to Cloud Run.
3.  Deploy the **Financial Advisor Agent** to Vertex AI Reasoning Engine.

## Project Structure

*   `src/governed_financial_advisor/`: Core Agent logic (LangGraph/ADK).
*   `src/gateway/`: The Gateway Service.
    *   `server/`: FastAPI entrypoint.
    *   `core/`: LLM client, tools, OPA client.
    *   `governance/nemo/`: **Consolidated NeMo Guardrails logic (Config, Actions, Manager).**
*   `deployment/`: Terraform and deployment scripts.

## License

Apache 2.0
