# Financial Advisor (Cybernetic Governance Edition)

**This repository implements the [Cybernetic Governance Framework](README_GOVERNANCE.md), transforming a probabilistic LLM agent into a deterministic, engineering-controlled system.**

## Overview

The Financial Advisor is a multi-agent system designed to assist human financial advisors. Unlike standard "tool-use" agents that can unpredictably call functions, this system uses a **Hierarchical Deterministic Markov Decision Process (HD-MDP)** and **Systems-Theoretic Process Analysis (STPA)** to guarantee safety constraints.

Use this authentic reference implementation to understand how to build **high-reliability agentic systems** for regulated industries.

## Core Capabilities

The architecture enforces "Defense in Depth" through six distinct layers (0-5), combining symbolic AI (Hard Logic) with Generative AI (Soft Logic):

1.  **Conversational Guardrails (Layer 0):** **NeMo Guardrails** ensures the model stays on topic and prevents jailbreaks before any tool execution.
2.  **Structural Validation (Layer 1):** Strict **Pydantic** schemas validate all inputs/outputs.
3.  **Policy Engine (Layer 2):** **Open Policy Agent (OPA)** enforces Role-Based Access Control (RBAC) and business logic (e.g., trading limits) external to the Python code.
4.  **Semantic Verification (Layer 3):** A specialized **Verifier Agent** audits the proposed actions of a "Worker" agent to prevent hallucinations (Propose-Verify-Execute pattern).
5.  **Consensus Engine (Layer 4):** Simulates an ensemble vote for high-stakes actions.
6.  **Deterministic Routing:** The `financial_coordinator` uses a strict router tool to transition between states, preventing invalid agent transitions.

For a deep dive into the theory and implementation, read **[README_GOVERNANCE.md](README_GOVERNANCE.md)**.

## Agent Team

The system orchestrates a team of specialized sub-agents:

1.  **Data Analyst Agent:** Performs market research using Google Search (accessed via Router).
2.  **Governed Trader Agent (Layer 3):**
    *   **Worker:** Proposes trading strategies based on analysis.
    *   **Verifier:** Audits the proposal against safety rules and the user's direct intent. Only the Verifier can execute.
3.  **Execution Analyst Agent:** Creates detailed execution plans (e.g., VWAP, TWAP).
4.  **Risk Analyst Agent:** Evaluates the overall portfolio risk and compliance.

## Quick Start

### 1. Prerequisites

*   [uv](https://github.com/astral-sh/uv) (for Python dependency management)
*   [Open Policy Agent (OPA)](https://www.openpolicyagent.org/docs/latest/#running-opa)

### 2. Installation

```bash
# Clone the repository
git clone <repository-url>
cd cybernetic-governance-engine

# Install dependencies
uv sync
```

### 3. Configuration

Copy the example environment file and configure your Google Cloud credentials:

```bash
cp .env.example .env
# Edit .env with your PROJECT_ID and OPA_URL (default: http://localhost:8181/v1/data/finance/allow)
```

### 4. Run OPA (Required)

You **must** have OPA running to execute trades setup. The system fails closed if OPA is unreachable.

```bash
# Run OPA in the background with the provided policy bundle
./opa run -s -b . --addr :8181 &
```

### 5. Run the Agent

```bash
adk run financial_advisor
```

## Deployment

The system is designed for **Google Cloud Run** using a multi-container Sidecar pattern.
*   **Container 1:** The Multi-Agent Application.
*   **Container 2:** OPA Sidecar (Policy Engine).
*   **Safety:** The app uses `dependsOn` to ensure the Policy Engine is healthy before starting.

See **[deployment/README.md](deployment/README.md)** for detailed deployment instructions.

## Architecture Diagram

<img src="financial-advisor.png" alt="Financial Advisor Architecture" width="800"/>
