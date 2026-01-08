# Financial Advisor (Cybernetic Governance Edition)

**This repository implements the [Cybernetic Governance Framework](README_GOVERNANCE.md), transforming a probabilistic LLM agent into a deterministic, engineering-controlled system.**

## Overview

The Financial Advisor is a governed agent system designed to assist human financial advisors. Unlike standard "tool-use" agents that can unpredictably call functions, this system uses a **Hierarchical Deterministic Markov Decision Process (HD-MDP)** and **Systems-Theoretic Process Analysis (STPA)** to guarantee safety constraints.

It has been migrated from Google ADK to **LangGraph + Redis** to enforce strict state transitions and persistence.

## High-Reliability Architecture

This system demonstrates a **Hybrid Cognitive Architecture** designed for regulated industries:

*   **Stateless Compute (Cloud Run):** The core agent logic runs on Google Cloud Run. This ensures **infinite scalability** (scale-to-zero) and **deterministic restarts** (no drift).
*   **Stateful Cognition (Redis):** Session state is persisted in **Redis** (Cloud Memorystore). This ensures that the conversation state (HD-MDP cursor) survives container restarts.
*   **Zero-Hop Policy (OPA Sidecar):** Regulatory checks happen over `localhost`. There is **no network latency** penalty for compliance, enabling high-frequency decision auditing.

The architecture enforces "Defense in Depth" through six distinct layers:

1.  **Conversational Guardrails (Layer 0):** **NeMo Guardrails** ensures the model stays on topic and validates inputs/outputs before they reach the core logic.
2.  **Structural Validation (Layer 2):** Strict **Pydantic** schemas validate all inputs/outputs.
3.  **Policy Engine (Layer 3):** **Open Policy Agent (OPA)** enforces Role-Based Access Control (RBAC) and business logic (e.g., trading limits) external to the Python code.
4.  **Deterministic Routing (Layer 4):** **LangGraph** enforces a strict state machine (Analysis -> Strategy -> Risk -> Execution), preventing invalid agent transitions.
5.  **Deterministic Tool Use (Layer 5):** Tools are invoked via code (Flow Engineering), not probabilistic LLM selection, for critical paths like Market Analysis.

For a deep dive into the theory and implementation, read **[README_GOVERNANCE.md](README_GOVERNANCE.md)**.

## Agent Team (Graph Nodes)

The system orchestrates a workflow of specialized nodes:

1.  **Market Analyst (Node):** Performs market research using Google Search (Deterministic Execution).
2.  **Strategist (Node):** Proposes trading strategies based on analysis.
3.  **Risk Guardian (Node):** Audits the proposal against safety rules and flags risks.
4.  **Governed Trader (Node):** Executes trades *only* if the OPA Policy Check passes (Hard Gate).

## Quick Start

### 1. Prerequisites

*   [uv](https://github.com/astral-sh/uv) (for Python dependency management)
*   [Open Policy Agent (OPA)](https://www.openpolicyagent.org/docs/latest/#running-opa)
*   Redis (or Docker container)

### 2. Installation

```bash
# Clone the repository
git clone <repository-url>
cd cybernetic-governance-engine

# Install dependencies
uv sync
```

### 3. Configuration

Copy the example environment file and configure your Google Cloud credentials and Redis URL:

```bash
cp .env.example .env
# Edit .env with your PROJECT_ID, GOOGLE_API_KEY, and OPA_URL
# Ensure REDIS_URL is set (default: redis://localhost:6379)
```

### 4. Run OPA (Required)

You **must** have OPA running to execute trades setup. The system fails closed if OPA is unreachable.

```bash
# Run OPA in the background with the provided policy bundle
./opa run -s -b . --addr :8181 &
```

### 5. Run the Agent (Server)

```bash
# Run the FastAPI server
uv run uvicorn financial_advisor.server:app --port 8080 --reload
```

### 6. Run the UI (Optional)

The repository includes a Streamlit-based web interface for interacting with the agent.

```bash
# Install Streamlit
uv pip install streamlit

# Run the UI (ensure the backend agent is running on port 8080)
streamlit run ui/app.py
```

### 7. Advanced Usage

#### A. Persistent User Memory
The UI supports persisting user context (via Redis) across sessions using URL parameters.
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
*   **Service 1 (Backend):** The LangGraph Agent Application + OPA Sidecar (Policy Engine).
*   **Service 2 (Frontend):** The Streamlit UI, automatically connected to the backend.
*   **Safety:** The app uses `dependsOn` to ensure the Policy Engine is healthy before starting.

See **[deployment/README.md](deployment/README.md)** for detailed deployment instructions.

## Architecture Diagram

<img src="financial-advisor.png" alt="Financial Advisor Architecture" width="800"/>
