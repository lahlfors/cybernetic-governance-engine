# Financial Advisor (Cybernetic Governance Edition)

**This repository implements the [Cybernetic Governance Framework](README_GOVERNANCE.md), transforming a probabilistic LLM agent into a deterministic, engineering-controlled system.**

## Overview

The Financial Advisor is a multi-agent system designed to assist human financial advisors. Unlike standard "tool-use" agents that can unpredictably call functions, this system uses a **Hierarchical Deterministic Markov Decision Process (HD-MDP)** and **Systems-Theoretic Process Analysis (STPA)** to guarantee safety constraints.

Use this authentic reference implementation to understand how to build **high-reliability agentic systems** for regulated industries.

## High-Reliability Architecture

This system demonstrates a **Hybrid Cognitive Architecture** designed for regulated industries:

*   **Stateless Compute (Cloud Run):** The core agent logic runs on Google Cloud Run. This ensures **infinite scalability** (scale-to-zero) and **deterministic restarts** (no drift).
*   **Stateful Cognition (Agent Engine):** Long-term memory is offloaded to **Vertex AI Agent Engine**. This allows the advisor to "know" the user for years, while the compute infrastructure remains ephemeral.
*   **Zero-Hop Policy (OPA Sidecar):** Regulatory checks happen over `localhost`. There is **no network latency** penalty for compliance, enabling high-frequency decision auditing.

The architecture enforces "Defense in Depth" through six distinct layers (0-5), combining symbolic AI (Hard Logic) with Generative AI (Soft Logic):

1.  **Conversational Guardrails (Layer 0):** **NeMo Guardrails** ensures the model stays on topic and prevents jailbreaks before any tool execution.
2.  **Cognitive Memory (Layer 1):** **Vertex AI Agent Engine** provides long-term, semantic memory (RAG) to maintain user context across stateless sessions.
3.  **Structural Validation (Layer 2):** Strict **Pydantic** schemas validate all inputs/outputs.
4.  **Policy Engine (Layer 3):** **Open Policy Agent (OPA)** enforces Role-Based Access Control (RBAC) and business logic (e.g., trading limits) external to the Python code.
5.  **Semantic Verification (Layer 4):** A specialized **Verifier Agent** audits the proposed actions of a "Worker" agent to prevent hallucinations (Propose-Verify-Execute pattern).
6.  **Consensus Engine (Layer 5):** Simulates an ensemble vote for high-stakes actions.
7.  **Deterministic Routing:** The `financial_coordinator` uses a strict router tool to transition between states, preventing invalid agent transitions.

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

### 6. Run the UI (Optional)

The repository includes a Streamlit-based web interface for interacting with the agent.

```bash
# Install Streamlit
uv pip install streamlit

# Run the UI (ensure the backend agent is running on port 8080)
streamlit run ui/app.py
```

```

### 7. Advanced Usage

#### A. Persistent User Memory
The UI supports persisting user context (via Vertex AI Memory Bank) across sessions using URL parameters.
*   **Default:** Random session ID (Memory is lost on refresh).
*   **Persistent:** Add `?user_id=[YOUR_ID]` to the URL.
    *   Example: `http://localhost:8501/?user_id=alice_trader`

#### B. Using Cloud Run Proxy (Recommended for Testing)
To test the backend directly without managing tokens manually, use the Google Cloud Proxy:

1.  **Start Proxy:**
    ```bash
    gcloud run services proxy governed-financial-advisor --project [PROJECT_ID] --region us-central1 --port 8080
    ```
2.  **Point UI to Proxy:**
    ```bash
    export BACKEND_URL="http://localhost:8080"
    streamlit run ui/app.py
    ```

## Deployment

The system is designed for **Google Cloud Run** using a multi-container Sidecar pattern.
*   **Service 1 (Backend):** The Multi-Agent Application + OPA Sidecar (Policy Engine).
*   **Service 2 (Frontend):** The Streamlit UI, automatically connected to the backend.
*   **Safety:** The app uses `dependsOn` to ensure the Policy Engine is healthy before starting.

See **[deployment/README.md](deployment/README.md)** for detailed deployment instructions.

## Architecture Diagram

<img src="financial-advisor.png" alt="Financial Advisor Architecture" width="800"/>
