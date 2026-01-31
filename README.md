# Financial Advisor (Cybernetic Governance Edition)

**This repository implements the [Cybernetic Governance Framework](README_GOVERNANCE.md), transforming a probabilistic LLM agent into a deterministic, engineering-controlled system.**

## Overview

The Financial Advisor is a multi-agent system designed to assist human financial advisors. Unlike standard "tool-use" agents that can unpredictably call functions, this system uses a **Hybrid Reasoning Architecture** combining deterministic workflow control with LLM-powered reasoning, guided by **Systems-Theoretic Process Analysis (STPA)** to guarantee safety constraints.

Use this authentic reference implementation to understand how to build **high-reliability agentic systems** for regulated industries.

<<<<<<< HEAD
=======
## Agentic DevOps & The Policy Governor

This implementation adheres to the **Agentic DevOps** philosophy, reframing the infrastructure as a deterministic supervisor.

👉 **See [docs/AGENTIC_DEVOPS_FEASIBILITY.md](docs/AGENTIC_DEVOPS_FEASIBILITY.md) for the full architectural analysis.**

*   **The Advisor (LLM):** The "Brain" that reasons about financial strategy.
*   **The Policy Governor:** The "Sentry" that enforces absolute boundaries ("The Wall"). Uses an **OPA Sidecar** for policy and **In-Process NeMo Guardrails** for semantic safety.
*   **The Currency Broker (HybridClient):** Manages the "Latency as Currency" budget, enforcing a strict Bankruptcy Protocol if reasoning takes too long.
*   **The Foundry (Pipelines):** Offline factories that compile STAMP hazards into Rego policies.

>>>>>>> origin/docs/agentic-gateway-analysis-15132879769016669359
## Hybrid Architecture: LangGraph + Google ADK

This system implements a **Hybrid Manager-Worker Architecture** that separates concerns:

| Layer | Technology | Responsibility |
|-------|------------|----------------|
| **Control Plane** | LangGraph | Deterministic workflow orchestration, conditional routing, state management |
| **Reasoning Plane** | Google ADK | LLM-powered agents with Vertex AI/Gemini for natural language understanding |
| **Bridge** | Adapters | Wraps ADK agents as LangGraph nodes, intercepts tool calls for routing |

```
┌─────────────────────────────────────────────────────────┐
│               LangGraph StateGraph                       │
│  ┌──────────┐    ┌────────────┐    ┌─────────────────┐ │
│  │Supervisor│───▶│Conditional │───▶│Risk Refinement  │ │
│  │  Node    │    │  Routing   │    │     Loop        │ │
│  └────┬─────┘    └────────────┘    └─────────────────┘ │
│       │                                                  │
├───────┼──────────────── ADAPTERS ───────────────────────┤
│       ▼                                                  │
│  ┌─────────┐  ┌─────────┐  ┌────────────┐ │
│  │  Data   │  │Execution│  │  Governed  │ │
│  │ Analyst │  │ Analyst │  │   Trader   │ │
│  └─────────┘  └─────────┘  └────────────┘ │
│               Google ADK LlmAgents                       │
└─────────────────────────────────────────────────────────┘
```

<<<<<<< HEAD
**Why Hybrid?**
- **LangGraph** excels at deterministic control flow—no LLM decides the execution path
- **Google ADK** excels at LLM reasoning—native agent patterns with Vertex AI integration
- **The Adapter Pattern** bridges them: ADK agents run inside LangGraph nodes, with tool calls intercepted to drive routing

👉 **For a deep dive, see [ARCHITECTURE.md](ARCHITECTURE.md)**

## Sovereign Stack (Phase 1 & 2)

This implementation adheres to the **Sovereign Stack** architecture, ensuring cloud independence and portability.

👉 **See [docs/SOVEREIGN_STACK.md](docs/SOVEREIGN_STACK.md) for full architecture details.**

*   **Cloud Agnostic:** Runs on local Docker, AWS, Azure, or On-Prem.
*   **Local Governance:** Policy (OPA) and Semantic Guardrails (NeMo) run as **Sidecars**.
*   **Standard Protocols:** Uses HTTP and **Unix Domain Sockets (UDS)** for ultra-low latency IPC.
*   **Optimistic Execution:** Uses Python `asyncio` to parallelize safety checks and tool execution, reducing latency.

=======
>>>>>>> origin/docs/agentic-gateway-analysis-15132879769016669359
## Governance & Safety (Green Stack)

This repository implements the advanced **Green Stack Governance Architecture**, separating cognition from control to satisfy ISO 42001 and STPA requirements.

👉 **Architecture Guide: [docs/GREEN_STACK_ARCHITECTURE.md](docs/GREEN_STACK_ARCHITECTURE.md)**

### The 4-Layer Safety Loop
1.  **Define (Risk Agent):** An offline "A2 Discovery" agent continuously scans for financial risks (e.g., Slippage, Drawdown) and defines Unsafe Control Actions (UCAs).
2.  **Verify (Evaluator Agent):** A dedicated "Proctor" subsystem audits agent traces against the STPA safety ontology and simulates adversarial attacks (Red Teaming). **[See Evaluator Agent Docs](src/evaluator_agent/README.md)**
3.  **Bridge (Transpiler):** A policy transpiler automatically converts discovered risks into executable code.
4.  **Enforce (NeMo Guardrails):** Real-time, deterministic Python actions intercept tool calls in <10ms to block unsafe actions. **[See Governance Logic Docs](src/governance/README.md)**

### Automated Pipeline
The entire risk discovery and rule deployment loop is automated via **Vertex AI Pipelines**.
👉 **Pipeline Docs: [src/pipelines/README.md](src/pipelines/README.md)**

## High-Reliability Architecture

This system demonstrates a **Hybrid Cognitive Architecture** designed for regulated industries:

*   **Stateless Compute (Cloud Run):** The core agent logic runs on Google Cloud Run. This ensures **infinite scalability** (scale-to-zero) and **deterministic restarts** (no drift).
*   **Redis State Store:** Session state is persisted to Redis (Cloud Memorystore) for reliable recovery across stateless compute instances.
*   **Zero-Hop Policy (OPA Sidecar):** Regulatory checks happen over `localhost` or UDS. There is **no network latency** penalty for compliance, enabling high-frequency decision auditing.

The architecture enforces "Defense in Depth" through six distinct layers (0-5), combining symbolic AI (Hard Logic) with Generative AI (Soft Logic):

1.  **Conversational Guardrails (Layer 0):** **NeMo Guardrails** ensures the model stays on topic and prevents jailbreaks before any tool execution.
2.  **Structural Validation (Layer 1):** Strict **Pydantic** schemas validate all inputs/outputs.
3.  **Policy Engine (Layer 2):** **Open Policy Agent (OPA)** enforces Role-Based Access Control (RBAC) and business logic (e.g., trading limits) external to the Python code.
4.  **Semantic Verification (Layer 3):** A specialized **Verifier Agent** audits the proposed actions of a "Worker" agent to prevent hallucinations (Propose-Verify-Execute pattern).
5.  **Consensus Engine (Layer 4):** Simulates an ensemble vote for high-stakes actions.
6.  **Deterministic Routing (LangGraph):** The system uses **LangGraph** to implement a strict State Graph, replacing probabilistic tool use with deterministic workflow control. This enforces the Strategy → Risk → Execution workflow and enables self-correcting loops.

For a deep dive into the theory and implementation, read **[README_GOVERNANCE.md](README_GOVERNANCE.md)**.

## Agent Team

The system orchestrates a team of specialized sub-agents, managed by a central **Supervisor Node**:

1.  **Data Analyst Agent:** Performs market research using Google Search.
2.  **Governed Trader Agent (Layer 3):**
    *   **Worker:** Proposes trading strategies based on analysis.
    *   **Verifier:** Audits the proposal against safety rules and the user's direct intent (delegating semantic checks to NeMo). Only the Verifier can execute.
3.  **Execution Analyst Agent (Strategy):** Creates detailed execution plans (e.g., VWAP, TWAP).
<<<<<<< HEAD
=======
4.  **Risk Analyst Agent (Offline):** A specialized A2 Discovery agent that runs asynchronously to identify UCAs and update policies, removed from the runtime hot path to minimize latency.
>>>>>>> origin/docs/agentic-gateway-analysis-15132879769016669359

## Quick Start (Sovereign Stack)

### 1. Prerequisites

*   [uv](https://github.com/astral-sh/uv) (for Python dependency management)
*   [Docker](https://docs.docker.com/get-docker/) & Docker Compose
<<<<<<< HEAD
*   [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (for GKE/TPU deployment)
=======
*   [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (for GKE deployment)
>>>>>>> origin/docs/agentic-gateway-analysis-15132879769016669359

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/lahlfors/cybernetic-governance-engine.git
cd cybernetic-governance-engine

# Install dependencies
uv sync
```

### 3. Configuration

Copy the example environment file and configure your Google Cloud credentials (for Vertex AI access):

```bash
cp .env.example .env
```

Edit `.env` with your settings:
```bash
# Model Configuration
MODEL_FAST=gemini-2.5-flash-lite
MODEL_REASONING=gemini-2.5-pro

# Vertex AI Configuration (Required for Reasoning Plane)
GOOGLE_GENAI_USE_VERTEXAI=1
GOOGLE_CLOUD_PROJECT=<YOUR_PROJECT_ID>
GOOGLE_CLOUD_LOCATION=<YOUR_REGION>
GOOGLE_API_KEY=<YOUR_API_KEY> # If using AI Studio

# Sovereign Stack Configuration
OPA_URL=http://localhost:8181/v1/data/finance/allow
# For UDS (Linux/Mac): OPA_URL=http+unix://%2Ftmp%2Fopa.sock/v1/data/finance/allow
```

### 4. Run the Stack (Docker Compose)

Start the governance infrastructure (OPA, Redis, NeMo):

```bash
docker-compose up -d
```

<<<<<<< HEAD
### 5. Run the Agent
=======
### 5. Run the Agentic Gateway (Required)

Start the gRPC Gateway service (Sidecar):

```bash
# Start in background or separate terminal
uv run python src/gateway/server/main.py
```
*Runs on port 50051.*

### 6. Run the Agent
>>>>>>> origin/docs/agentic-gateway-analysis-15132879769016669359

```bash
# Run the FastAPI server locally
uv run python src/server.py
```

The server will start on `http://localhost:8080`.

<<<<<<< HEAD
### 6. Run the UI (Optional)
=======
### 7. Run the UI (Optional)
>>>>>>> origin/docs/agentic-gateway-analysis-15132879769016669359

```bash
# Install Streamlit
uv pip install streamlit

# Run the UI
export BACKEND_URL="http://localhost:8080"
streamlit run ui/app.py
```

<<<<<<< HEAD
## Production Deployment (GKE & TPU)

This repository supports deploying the high-performance inference stack to Google Kubernetes Engine (GKE) using either NVIDIA GPUs or Google TPUs.

### Deployment Options

The `deploy_all.py` script automates the entire process, including provisioning infrastructure, building containers, and deploying manifests.
=======
## Production Deployment (GKE)

This repository supports deploying the high-performance inference stack to Google Kubernetes Engine (GKE) using NVIDIA GPUs.

### Deployment Options

The `deploy_sw.py` script automates the entire process, including building containers and deploying manifests.
>>>>>>> origin/docs/agentic-gateway-analysis-15132879769016669359

#### Option A: NVIDIA H100 (Default)
Optimized for ultra-low latency using **Speculative Decoding**. Best for user-facing applications requiring strict SLAs (<200ms TTFT).

```bash
<<<<<<< HEAD
python3 deployment/deploy_all.py \
=======
python3 deployment/deploy_sw.py \
>>>>>>> origin/docs/agentic-gateway-analysis-15132879769016669359
    --project-id <YOUR_PROJECT_ID> \
    --region us-central1 \
    --accelerator gpu
```

<<<<<<< HEAD
#### Option B: Google TPU v5e (Cost Optimized)
Uses **TPU v5e** (8 chips) with XLA/Pallas backend. significantly cheaper (~80%) but currently lacks Speculative Decoding support. Recommended for offline batch workloads.

```bash
python3 deployment/deploy_all.py \
    --project-id <YOUR_PROJECT_ID> \
    --region us-central1 \
    --accelerator tpu
```

👉 **See [docs/TPU_MIGRATION_ANALYSIS.md](docs/TPU_MIGRATION_ANALYSIS.md) for a detailed architectural comparison.**

=======
>>>>>>> origin/docs/agentic-gateway-analysis-15132879769016669359
## Security Verification (Red Teaming)

This project includes a comprehensive **Red Team Test Suite** to verify the robustness of guardrails against adversarial attacks.

To run the automated security tests against a deployed agent:

```bash
# 1. Ensure backend is running
# 2. Run the test suite
python3 tests/red_team/run_red_team.py
```

The suite tests for:
*   ✅ Jailbreaks (DAN, Roleplay)
*   ✅ Role Escalation
*   ✅ Verifier Bypass
*   ✅ Illegal Financial Advice
*   ✅ Prompt Injection

👉 **See [tests/red_team/README.md](tests/red_team/README.md) for full documentation.**

### Compliance (ISO 42001)

The system is designed to meet **ISO/IEC 42001** standards for AI Management Systems.
👉 **See [ISO_42001_COMPLIANCE.md](ISO_42001_COMPLIANCE.md) for the Telemetry Audit Map.**

## Architecture Diagram

<img src="financial-advisor.png" alt="Financial Advisor Architecture" width="800"/>

## License

This project is licensed under the Apache 2.0 License - see the `LICENSE` file for details.

**FSA Code Guidance:** This solution uses open-source dependencies compliant with Google FSA policies (Apache 2.0, MIT). The codebase is designed for internal prototyping and requires formal review before customer distribution or production use.
