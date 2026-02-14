# Financial Advisor (Sovereign Governance Edition)

**This repository implements the [Cybernetic Governance Framework](README_GOVERNANCE.md), transforming a probabilistic LLM agent into a deterministic, engineering-controlled system.**

## Overview

The Financial Advisor is a multi-agent system designed to assist human financial advisors. Unlike standard "tool-use" agents that can unpredictably call functions, this system uses a **Hybrid Reasoning Architecture** combining deterministic workflow control with LLM-powered reasoning, guided by **Systems-Theoretic Process Analysis (STPA)** to guarantee safety constraints.

Use this authentic reference implementation to understand how to build **high-reliability agentic systems** for regulated industries.

## Agentic DevOps & The Policy Governor

This implementation adheres to the **Agentic DevOps** philosophy, reframing the infrastructure as a deterministic supervisor.

👉 **See [ARCHITECTURE.md](ARCHITECTURE.md) for the full architectural analysis.**

*   **The Advisor (LLM):** The "Brain" that reasons about financial strategy (DeepSeek R1 Distill).
*   **The Policy Governor:** The "Sentry" that enforces absolute boundaries ("The Wall"). Uses an **OPA Sidecar** for policy and **In-Process NeMo Guardrails** for semantic safety.
    *   **New:** See **[Neuro-Symbolic Governance](docs/NEURO_SYMBOLIC_GOVERNANCE.md)** for the architectural combination of **Residual-Based Control (RBC)** and **Optimization-Based Control (OPC)**.
*   **The Currency Broker (GatewayClient):** Manages the "Latency as Currency" budget, enforcing a strict Bankruptcy Protocol if reasoning takes too long.
*   **The Foundry (Pipelines):** Offline factories that compile STAMP hazards into Rego policies.

## Sovereign Split-Brain Architecture

This implementation adheres to the **Sovereign Stack** architecture, ensuring cloud independence and portability. It utilizes a "Split-Brain" topology to optimize for both complex reasoning and low-latency governance.

| Node | Model | Responsibility |
|------|-------|----------------|
| **Node A (The Brain)** | `DeepSeek-R1-Distill-Qwen-32B` | Complex reasoning, planning, and analysis. High intelligence, higher latency. |
| **Node B (The Police)** | `Qwen2.5-7B-Instruct` | Fast governance checks, FSM enforcement, JSON formatting. Ultra-low latency (<50ms). |

👉 **See [ARCHITECTURE.md](ARCHITECTURE.md) for full architecture details.**

*   **Cloud Agnostic:** Runs on local Docker/K8s with vLLM. No dependence on proprietary cloud APIs.
*   **Local Governance:** Policy (OPA) and Semantic Guardrails (NeMo) run as **Sidecars**.
*   **Gateway Client:** A smart client in the Gateway routes traffic between Node A and Node B based on task complexity.

## Governance & Safety (Green Stack)

This repository implements the advanced **Green Stack Governance Architecture**, separating cognition from control to satisfy ISO 42001 and STPA requirements.

👉 **Architecture Guide: [ARCHITECTURE.md](ARCHITECTURE.md)**

### The 4-Layer Safety Loop
1.  **Define (Risk Agent):** An offline "A2 Discovery" agent continuously scans for financial risks (e.g., Slippage, Drawdown) and defines Unsafe Control Actions (UCAs).
2.  **Verify (Evaluator Agent):** A dedicated "Proctor" subsystem audits agent traces against the STPA safety ontology and simulates adversarial attacks (Red Teaming). **[See Evaluator Agent Docs](src/governed_financial_advisor/evaluator_agent/README.md)**
3.  **Bridge (Transpiler):** A policy transpiler automatically converts discovered risks into executable code.
4.  **Enforce (NeMo Guardrails):** Real-time, deterministic Python actions intercept tool calls in <10ms to block unsafe actions. **[See Governance Logic Docs](src/governed_financial_advisor/governance/README.md)**

## Quick Start (Sovereign Stack)

### 1. Prerequisites

*   [uv](https://github.com/astral-sh/uv) (for Python dependency management)
*   [Docker](https://docs.docker.com/get-docker/) & Docker Compose
*   **GPU Resources**: Requires at least one NVIDIA GPU (L4 recommended) for vLLM services.

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/lahlfors/cybernetic-governance-engine.git
cd cybernetic-governance-engine

# Install dependencies
uv sync
```

### 3. Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Ensure `.env` points to your local or K8s vLLM services:

```bash
# Node A: The Brain
MODEL_REASONING=deepseek-ai/DeepSeek-R1-Distill-Qwen-32B
VLLM_REASONING_API_BASE=http://localhost:8000/v1

# Node B: The Police
MODEL_FAST=Qwen/Qwen2.5-7B-Instruct
VLLM_FAST_API_BASE=http://localhost:8001/v1

# Governance
OPA_URL=http://localhost:8181/v1/data/finance/allow
```

### 4. Run the Stack (Docker Compose / K8s)

For local development with Docker Compose (simulating the stack):

```bash
docker-compose up -d
```

For Kubernetes deployment (Production):

```bash
kubectl apply -f deployment/k8s/
```

### 5. Run the Agentic Gateway (Required)

Start the gRPC Gateway service (Sidecar):

```bash
# Start in background or separate terminal
uv run python src/gateway/server/main.py
```
*Runs on port 50051.*

### 6. Run the Agent

```bash
# Run the FastAPI server locally
uv run python src/governed_financial_advisor/server.py
```

The server will start on `http://localhost:8080`.

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
👉 **See [docs/ISO_42001_COMPLIANCE.md](docs/ISO_42001_COMPLIANCE.md) for the Telemetry Audit Map.**

## License

This project is licensed under the Apache 2.0 License - see the `LICENSE` file for details.
