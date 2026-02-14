# Governed Financial Advisor (Sovereign Edition)

An AI-driven financial agent designed to demonstrate **safe, governed, and performant** autonomous behavior. This system implements a "Sovereign" architecture where reasoning and governance run on independent, locally-controlled infrastructure (vLLM/Llama 3), reinforced by neuro-symbolic guardrails.

## Key Features

*   **Sovereign Architecture:** "Split-Brain" topology separating Reasoning (Llama 3.1 8B) from Governance (Llama 3.2 3B).
*   **Neuro-Symbolic Governance:** Enforces SR 11-7 and ISO 42001 compliance using OPA policies, STPA hazard analysis, and circuit breakers.
*   **Hybrid Observability:**
    *   **Application Layer:** Async LangSmith tracing for prompt engineering and execution trees.
    *   **System Layer:** AgentSight (eBPF sidecar) for deep payload inspection and security monitoring (syscalls).
*   **Optimistic Execution:** Parallel "Planner-Evaluator-Executor" loop with Redis-based interrupt signals.

## Architecture

See `docs/GATEWAY_ARCHITECTURE.md` for a detailed breakdown.

### Observability Stack

We employ a **Hybrid Strategy** to balance latency and visibility:
1.  **LangSmith (Async):** Captures high-level application flow (Chain of Thought, Tool Use) without blocking the main event loop.
2.  **AgentSight (Kernel):** An eBPF daemon runs alongside the application, intercepting encrypted traffic and system calls to detect unauthorized actions and correlate them with high-level intent via injected `X-Trace-Id` headers.

## Getting Started

### Prerequisites
*   Docker & Docker Compose
*   Python 3.10+
*   Poetry or uv (for dependency management)

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/google/governed-financial-advisor.git
    cd governed-financial-advisor
    ```

2.  **Install Dependencies:**
    ```bash
    uv sync --group dev
    ```

3.  **Configure Environment:**
    Copy `.env.example` to `.env` and set your keys (Alpaca, LangSmith, etc.).

### Running the System

**Option 1: Full Stack (with AgentSight)**
To run the advisor with full system-level observability:

```bash
cd deployment/agentsight
docker-compose -f docker-compose.agentsight.yaml up --build
```
Access the AgentSight dashboard at `http://localhost:3000`.

**Option 2: Local Development**
```bash
# Start infrastructure (Redis, vLLM)
docker-compose up -d redis vllm-reasoning vllm-governance

# Run the Agent
python src/main.py
```

## Documentation

*   [AgentSight Analysis](docs/AGENTSIGHT_ANALYSIS.md)
*   [Gateway Architecture](docs/GATEWAY_ARCHITECTURE.md)
*   [Governance Crosswalk](docs/GOVERNANCE_CROSSWALK.md)
