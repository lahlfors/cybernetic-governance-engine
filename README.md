# Financial Advisor (Sovereign Engine Edition)

**This repository implements the "Sovereign Engine" framework, a high-reliability, cloud-agnostic architecture for Agentic AI.**

## Overview

The Financial Advisor is a multi-agent system designed to assist human financial advisors. Unlike standard "tool-use" agents that can unpredictably call functions, this system uses a **Hybrid Reasoning Architecture** combining deterministic workflow control with LLM-powered reasoning, guided by **Systems-Theoretic Process Analysis (STPA)** to guarantee safety constraints.

Use this authentic reference implementation to understand how to build **high-reliability agentic systems** for regulated industries using a purely sovereign stack (no external API dependencies).

## Sovereign Architecture: Split-Brain vLLM

This implementation adheres to the **Sovereign Stack** architecture, ensuring absolute control over inference and data.

👉 **See [docs/GATEWAY_ARCHITECTURE.md](docs/GATEWAY_ARCHITECTURE.md) for the full architectural analysis.**

### The Split-Brain Topology
The system separates "Thinking" from "Governing" into two distinct vLLM services to optimize for cost and latency:

1.  **Node A: The Brain (Reasoning Plane)**
    *   **Model:** `meta-llama/Meta-Llama-3.1-8B-Instruct`
    *   **Role:** Complex logic, Chain-of-Thought (CoT), Planning, and Data Analysis.
    *   **Hardware:** Dedicated GPU (e.g., NVIDIA L4).
    *   **Service:** `vllm-reasoning`

2.  **Node B: The Police (Governance Plane)**
    *   **Model:** `meta-llama/Llama-3.2-3B-Instruct`
    *   **Role:** Fast FSM checks, JSON schema validation, Policy enforcement, and Chat.
    *   **Hardware:** Shared GPU or High-Performance CPU.
    *   **Service:** `vllm-governance`

### Computer Use (Sandboxed Execution)
The system implements a **Computer Use** capability where the Data Analyst agent writes and executes Python code instead of relying on pre-defined tools.

*   **Sandbox Sidecar:** A lightweight FastAPI service (`src/sandbox/main.py`) runs alongside the agent.
*   **Security:** Code execution is isolated in a container with restricted network access, pre-loaded with `pandas` and `yfinance`.
*   **Workflow:** Agent writes code -> Gateway sends to Sandbox -> Sandbox executes & returns STDOUT/STDERR -> Agent interprets result.

## Core Components

*   **The Gateway (GatewayClient):** A unified client that intelligently routes requests to the appropriate vLLM node based on the task mode (Reasoning vs. Governance).
*   **The Policy Governor (OPA):** An **Open Policy Agent** sidecar that enforces business logic and regulatory compliance (e.g., "No trading in restricted regions").
*   **The Agent (Google ADK):** The application logic layer, refactored to use the `GatewayClient` for all LLM interactions.

## Quick Start (Sovereign Stack)

### 1. Prerequisites

*   [uv](https://github.com/astral-sh/uv) (for Python dependency management)
*   [Docker](https://docs.docker.com/get-docker/) & Docker Compose
*   [Kubernetes](https://kubernetes.io/) (Minikube, Kind, or GKE)

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/lahlfors/cybernetic-governance-engine.git
cd cybernetic-governance-engine

# Install dependencies
uv sync
```

### 3. Configuration

The system is pre-configured for the Sovereign Stack. Copy the `.env.example` (or use the provided defaults):

```bash
cp .env.example .env
```

**Key Settings (Defaults):**
```bash
# Split-Brain URLs
VLLM_REASONING_API_BASE=http://vllm-reasoning:8000/v1
VLLM_FAST_API_BASE=http://vllm-governance:8000/v1

# Sandbox
SANDBOX_URL=http://localhost:8081/execute
```

### 4. Run the Infrastructure (Kubernetes)

Deploy the sovereign stack to your Kubernetes cluster:

```bash
# Apply Manifests
kubectl apply -f deployment/k8s/
```

This will spin up:
- `vllm-reasoning` (Llama 3.1 8B)
- `vllm-governance` (Llama 3.2 3B)
- `governed-financial-advisor` (Agent + OPA + Sandbox)
- `redis` (State Store)

### 5. Local Development (Docker Compose)

For local testing without K8s, use Docker Compose (Note: Requires GPU support or CPU offloading):

```bash
docker-compose up -d
```

### 6. Run the Agent Locally

To run the agent logic locally while connecting to the infrastructure:

```bash
# Start the Gateway (if not running in K8s)
uv run python src/gateway/server/main.py

# Start the Agent Server
uv run python src/governed_financial_advisor/server.py
```

## Security & Governance

This project implements "Defense in Depth" using a **Neuro-Symbolic Governance** approach:

1.  **Structural Validation:** Pydantic schemas enforce input/output formats.
2.  **Policy Engine:** OPA enforces RBAC and business rules.
3.  **Sandboxed Execution:** Arbitrary code execution is confined to the ephemeral sandbox container.
4.  **Split-Brain Verification:** The "Governance" node can be used to verify the outputs of the "Reasoning" node (Propose-Verify-Execute).

## License

This project is licensed under the Apache 2.0 License - see the `LICENSE` file for details.
