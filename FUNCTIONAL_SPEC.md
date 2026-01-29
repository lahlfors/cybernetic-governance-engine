# Functional Specification & Technical Architecture

## 1. System Overview

The **Governed Financial Advisor** is a high-reliability agentic system designed for regulated financial environments. It implements a **Hybrid Architecture** that combines deterministic workflow orchestration (LangGraph) with probabilistic reasoning agents (Google ADK).

The system follows the **"Green Stack"** governance pattern, separating the **Control Plane** (Routing/Safety) from the **Reasoning Plane** (LLM Logic).

## 2. Technical Architecture

### 2.1. Hybrid Control Plane (LangGraph)
*   **Entry Point**: `src/governed_financial_advisor/server.py` hosts a FastAPI application.
*   **Orchestration**: `src/governed_financial_advisor/graph/graph.py` defines a deterministic State Graph using `langgraph`.
*   **Supervisor Node**: The root node (`supervisor_node`) calls the ADK Supervisor Agent and intercepts `route_request` tool calls to determine the `next_step` state transition.
*   **Adapters**: `src/governed_financial_advisor/graph/nodes/adapters.py` provides the bridge between the synchronous/async LangGraph nodes and the streaming/event-driven Google ADK agents (`run_adk_agent`).

### 2.2. Reasoning Plane (Google ADK)
*   **Agents**: Located in `src/governed_financial_advisor/agents/`.
*   **Governed Trader**: Implements a `SequentialAgent` pattern:
    1.  **Worker**: Proposes trading strategies.
    2.  **Verifier**: Validates strategies using `verify_with_nemo_guardrails` before execution.
*   **Risk Analyst**: A stateless, specialized agent (`src/governed_financial_advisor/agents/risk_analyst/agent.py`) that identifies Unsafe Control Actions (UCAs).
    *   **Governance Sandwich**: Uses `GovernanceClient` to enforce strict JSON output schema (`RiskAssessment`) via a self-hosted vLLM instance.
    *   **Offline Status**: Removed from the runtime hot path; used primarily for offline policy discovery or asynchronous checks.
*   **Execution Analyst**: Generates detailed, deterministic JSON execution plans.

### 2.3. Governance Layer ("The Green Stack")
*   **NeMo Guardrails**:
    *   **In-Process**: The main application (`server.py`) loads rails *in-process* via `src/governed_financial_advisor/utils/nemo_manager.py` for input validation (`validate_with_nemo`).
    *   **Sidecar (Standalone)**: A separate server (`src/governed_financial_advisor/governance/nemo_server.py`) exists to serve rails via HTTP, but is **not** currently used by the main application.
*   **Open Policy Agent (OPA)**:
    *   **Sidecar**: The system relies on an external OPA server (simulated or deployed as a sidecar).
    *   **Client**: `src/governed_financial_advisor/governance/client.py` connects to OPA via HTTP/TCP (`httpx`) to enforce RBAC and trade policies.
*   **Policy Transpiler**: Converts high-level STAMP hazards into executable Rego and Python policies.

### 2.4. Infrastructure & Telemetry
*   **Hybrid Client**: `src/governed_financial_advisor/infrastructure/llm_client.py` routes traffic between a "Fast Path" (Self-hosted vLLM) and a "Reliable Path" (Vertex AI) based on TTFT (Time To First Token) SLAs and connection health.
*   **Redis**: `src/governed_financial_advisor/infrastructure/redis_client.py` provides persistence for graph checkpoints and safety state (Control Barrier Functions), falling back to in-memory storage if connection fails.
*   **Telemetry**: Extensive OpenTelemetry instrumentation tags traces with ISO 42001 attributes (e.g., `enduser.id`, `risk.verdict`, `governance.decision`).

## 3. Component Wiring Diagram

```mermaid
graph TD
    User[User / Client] -->|HTTP POST /agent/query| Server[server.py]

    subgraph "Control Plane (In-Process)"
        Server -->|Validates| NeMo_Local[NeMo Manager (Local)]
        Server -->|Invokes| Graph[LangGraph Workflow]

        Graph --> Supervisor[Supervisor Node]
        Graph --> Safety[Optimistic Safety Node]

        Supervisor -->|Routes| Adapter[ADK Adapter Layer]
    end

    subgraph "Reasoning Plane (Google ADK)"
        Adapter --> Trader[Governed Trader Agent]
        Adapter --> Planner[Execution Analyst Agent]

        Trader -->|Worker| Gemini[Vertex AI Gemini]
        Trader -->|Verifier| Gemini
        Planner -->|JSON| Gemini
    end

    subgraph "Governance Services"
        Trader -.->|Checks| OPA[OPA Sidecar (HTTP)]
        NeMo_Local -.->|Custom Actions| Actions[Python Actions]

        RiskAnalyst[Risk Analyst Agent] -.->|Strict JSON| vLLM[vLLM Service]
    end

    subgraph "Infrastructure"
        Graph -->|Checkpoints| Redis[Redis / Memorystore]
        Safety -->|CBF State| Redis
    end
```

## 4. Gap Analysis (Documentation vs. Code)

### 4.1. NeMo Sidecar Architecture
*   **Documentation**: Describes a "Sidecar" architecture where NeMo runs as a separate service to ensure isolation.
*   **Code**: `src/governed_financial_advisor/server.py` initializes NeMo **in-process** (`nemo_manager.load_rails()`). While a sidecar server exists (`nemo_server.py`), the main application does not use it, creating a coupling risk and deviating from the "Zero-Hop" sidecar promise for this specific component.

### 4.2. Risk Analyst Integration
*   **Documentation**: Often implies the Risk Analyst is part of the runtime loop (though `GAP_ANALYSIS_REPORT.md` correctly notes it was moved).
*   **Code**: Confirms `Risk Analyst` is commented out in `graph.py` and runs offline. The runtime safety is handled by the `Optimistic Execution Node` and deterministic rules, not the LLM-based Risk Analyst.

### 4.3. "ADK Native" vs. Hybrid
*   **Memory/Context**: Suggested an "ADK Native" model might be expected.
*   **Code**: Fully implements the **Hybrid Model**. LangGraph is the authoritative orchestrator, wrapping ADK agents as tools/nodes. This is a robust implementation but differs from a pure "Multi-Agent Framework" approach.

### 4.4. Semantic Checks
*   **Documentation**: Mentions extensive semantic verification (PII, Jailbreaks).
*   **Code**: NeMo rails are configured primarily for **Financial Risk** (Drawdown, Latency). Semantic checks rely on standard/default NeMo flows, with no explicit custom flows for advanced PII or toxicity found in the application logic itself (implicit in NeMo defaults).

## 5. Summary
The software is a mature implementation of the **Hybrid Agentic Governance** pattern. It successfully integrates deterministic control (LangGraph/OPA) with probabilistic reasoning (Gemini/ADK). The primary architectural discrepancy is the **In-Process loading of NeMo Guardrails** versus the documented Sidecar approach.
