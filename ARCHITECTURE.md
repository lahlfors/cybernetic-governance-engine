<<<<<<< HEAD
# Architecture: Hybrid LangGraph + Google ADK + Hybrid Inference + In-Process Governance

This document describes the hybrid architecture of the Cybernetic Governance Engine, which combines **LangGraph** for deterministic workflow orchestration with **Google ADK** for LLM-powered agent reasoning, supported by a **Hybrid Inference Stack** (vLLM + Vertex AI) and specialized **In-Process Governance**.

## Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CONTROL PLANE (Deterministic)                     │
│                                  LangGraph                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌──────────────┐ │
│  │  Supervisor │───▶│ Conditional │───▶│    Risk     │───▶│  Refinement  │ │
│  │    Node     │    │   Routing   │    │   Router    │    │     Loop     │ │
│  └─────────────┘    └─────────────┘    └─────────────┘    └──────────────┘ │
├─────────────────────────────────────────────────────────────────────────────┤
│                                  ADAPTERS                                   │
│                        (Bridge: LangGraph ↔ ADK)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                          REASONING PLANE (Probabilistic)                    │
│                               Google ADK                                    │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌──────────────┐ │
│  │    Data     │    │  Execution  │    │    Risk     │    │   Governed   │ │
│  │   Analyst   │    │   Analyst   │    │   Analyst   │    │    Trader    │ │
│  └─────────────┘    └─────────────┘    └─────────────┘    └──────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Why Hybrid?

| Concern | LangGraph | Google ADK |
|---------|-----------|------------|
| **Workflow Control** | ✅ Deterministic state machine | ❌ Probabilistic tool calls |
| **LLM Reasoning** | ❌ Manual prompt chaining | ✅ Native agent patterns |
| **Observability** | ✅ Explicit graph tracing | ✅ Built-in telemetry |
| **Checkpointing** | ✅ Redis/memory savers | ✅ Session service |

## In-Process Governance (The "Governance Sandwich")

We implement a strict separation of concerns to guarantee safety and structure without sacrificing reasoning depth.

### 1. The Brain (Reasoning)
*   **Model:** `gemini-2.5-pro` (Vertex AI).
*   **Role:** Complex analysis, document understanding, and "System 2" thinking.
*   **Safety:** Wrapped by NeMo Guardrails for semantic policy checks (e.g., preventing toxicity).

### 2. The Enforcer (Structure)
*   **Model:** `google/gemma-2-9b-it` (Self-Hosted on GKE with NVIDIA L4).
*   **Role:** Syntactic enforcement of JSON schemas via Finite State Machines (FSM).
*   **Technique:** We use vLLM's `guided_json` with **Prefix Caching** to achieve low-latency (<50ms) schema validation.
*   **Why:** A smaller, instruction-tuned model running locally is faster and more deterministic for formatting tasks than a large reasoning model.

This pattern ensures **Zero-Hallucination Structure** while leveraging **SOTA Reasoning Capabilities**.

---

## Observability & Tracing (Langfuse)

We use **[Langfuse](https://langfuse.com/)** (self-hosted in-cluster) as the centralized observability platform for the entire hybrid stack.

*   **Endpoint:** `http://langfuse-web.langfuse.svc.cluster.local:4317` (OTLP)
*   **Coverage:**
    1.  **LangGraph Control Plane:** Captures state transitions and routing decisions.
    2.  **Google ADK Agents:** Captures reasoning chains and tool invocations via OpenTelemetry instrumentation.
    3.  **vLLM (The Enforcer):** Captures token generation metrics (TTFT, ITL) and schema validation success/failure. We inject `OTEL_SERVICE_NAME=vllm-inference` to distinguish governance traces.

This unified view allows us to correlate "high-level intent" (Gemini) with "low-level enforcement" (vLLM) in a single trace.

---

## Component Breakdown

### 1. LangGraph Orchestration (`src/graph/`)

**Purpose**: Deterministic workflow control—no LLM decides the flow.

| File | Responsibility |
|------|----------------|
| `graph.py` | Defines the `StateGraph` with nodes, edges, and conditional routing |
| `state.py` | Typed state schema (`AgentState`) with message history and control signals |
| `router.py` | Helper functions for conditional edge logic |
| `checkpointer.py` | Redis-backed or in-memory persistence for conversation state |

**Key Pattern: Conditional Edges**
```python
workflow.add_conditional_edges("risk_analyst", risk_router, {
    "execution_analyst": "execution_analyst",  # Loop back if rejected
    "governed_trader": "governed_trader"       # Proceed if approved
})
```

### 2. Google ADK Agents (`src/agents/`)

**Purpose**: LLM-powered reasoning with Vertex AI/Gemini.

```
src/agents/
├── financial_advisor/
│   ├── agent.py            # Coordinator (Root Agent)
│   └── callbacks.py        # OTel Interceptor (ISO 42001)
├── data_analyst/agent.py   # Market research agent
├── execution_analyst/agent.py  # Strategy planning agent
├── risk_analyst/agent.py   # Risk evaluation agent
└── governed_trader/agent.py    # Trade execution with Propose-Verify pattern
```

Each agent is a `google.adk.agents.LlmAgent` with:
- Custom instructions
- Specialized tools
- Model configuration (Gemini via Vertex AI)

### 3. The Adapter Layer (`src/graph/nodes/adapters.py`)

**Purpose**: Bridge between LangGraph's sync node functions and ADK's async runners.

```python
def run_adk_agent(agent_instance, user_msg: str, session_id: str, user_id: str):
    """Execute an ADK agent and return results for LangGraph."""
    
    # 1. Ensure session exists
    asyncio.run(ensure_session())
    
    # 2. Create Runner
    runner = Runner(agent=agent_instance, session_service=session_service)
    
    # 3. Execute and collect events
    for event in runner.run(user_id, session_id, new_message):
        # Extract text and function calls
        ...
    
    return AgentResponse(answer=..., function_calls=...)
```

---

## The Supervisor Pattern

The Supervisor Node is the "brain" that:
1. **Runs the ADK root agent** to understand user intent
2. **Intercepts tool calls** (specifically `route_request`) to determine routing
3. **Returns a control signal** (`next_step`) that LangGraph uses for deterministic routing

```python
def supervisor_node(state):
    # 1. Run the coordinator agent
    response = run_adk_agent(root_agent, last_msg)

    # 2. Intercept routing tool call
    for call in response.function_calls:
        if call.name == "route_request":
            target = call.args.get("target")
            # Map to graph node
            if "data" in target.lower():
                next_step = "data_analyst"
            ...

    # 3. Return control signal for LangGraph
    return {"messages": [...], "next_step": next_step}
```

This pattern ensures:
- ✅ The LLM decides **intent** (what the user wants)
- ✅ The graph decides **execution** (how to fulfill it)

---

## Risk Refinement Loop

A key feature is the **self-correcting loop** between the Execution Analyst and Risk Analyst:

```mermaid
graph LR
    EA[Execution Analyst] -->|Strategy| RA[Risk Analyst]
    RA -->|APPROVED| GT[Governed Trader]
    RA -->|REJECTED_REVISE| EA

    style RA fill:#f9f,stroke:#333
    style EA fill:#bbf,stroke:#333
```

**How it works**:
1. Execution Analyst proposes a strategy
2. Risk Analyst evaluates (heuristic keyword detection: "high risk", "reject", etc.)
3. If rejected, LangGraph routes back to Execution Analyst with feedback injected
4. Loop continues until approved or escalated to human review

---

## Deployment Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Cloud Run Service                         │
│  ┌─────────────────────┐    ┌────────────────────────────┐  │
│  │   Main Container    │    │    OPA Sidecar (Layer 2)   │  │
│  │   ───────────────   │    │    ────────────────────    │  │
│  │   FastAPI Server    │◀──▶│    Policy Enforcement      │  │
│  │   LangGraph         │    │    finance_policy.rego     │  │
│  │   ADK Agents        │    └────────────────────────────┘  │
│  │   NeMo Guardrails   │                                     │
│  └──────────┬──────────┘                                     │
│             │                                                 │
│             ▼                                                 │
│  ┌─────────────────────┐                                     │
│  │   Redis (State)     │                                     │
│  │   Cloud Memorystore │                                     │
│  └─────────────────────┘                                     │
└──────────────────────────────────────────────────────────────┘
```

**State Management (Dual Redis Strategy):**
1.  **Application State:** Uses **Google Cloud Memorystore** (External). Stores LangGraph conversation checkpoints (`AgentState`) and session history. Credentials injected via `REDIS_URL`.
2.  **Observability State:** Uses **Langfuse Internal Redis**. Deployed as a sidecar container within the Langfuse Helm chart on GKE. Used strictly for trace ingestion buffering and caching.

**Environment Variables**:
| Variable | Purpose |
|----------|---------|
| `GOOGLE_GENAI_USE_VERTEXAI=true` | Use Vertex AI instead of API key |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | Region (e.g., `us-central1`) |
| `REDIS_URL` | Redis connection for state persistence |
| `MODEL_FAST` | Fast model alias (e.g., `gemini-2.5-flash-lite`) |
| `MODEL_REASONING` | Reasoning model alias (e.g., `gemini-2.5-pro`) |

---

## See Also

- [README_GOVERNANCE.md](README_GOVERNANCE.md) - Governance framework theory
- [STPA_ANALYSIS.md](STPA_ANALYSIS.md) - Safety analysis
- [deployment/README.md](deployment/README.md) - Deployment guide
=======
# Architecture: MACAW + Cybernetic Governance

This document describes the **Cybernetic Governance Architecture** of the Financial Advisor system, aligned with **ISO/IEC 42001** and Capital One's **MACAW** framework.

For a detailed guide on the architectural refactoring, see [MACAW_REFACTOR_GUIDE.md](docs/MACAW_REFACTOR_GUIDE.md).

## 1. The Cybernetic Model (Viable System Model)

The system is designed not just as a software pipeline, but as a **Cybernetic Control System** that ensures safety through Feedback, Feedforward, and Requisite Variety.

| VSM System | Role | Component | Function |
| :--- | :--- | :--- | :--- |
| **System 5** | Identity / Policy | **Constitution** | Defines high-level goals ("Helpful & Harmless") and risk policies. |
| **System 4** | Intelligence / Feedforward | **Execution Analyst (Planner)** | Anticipates future states; generates plans; simulates outcomes (via Evaluator). |
| **System 3** | Control / Optimization | **Evaluator Agent** | The "Internal Regulator". Enforces constraints via simulation and policy checks. |
| **System 2** | Coordination | **Graph State & Schema** | Ensures data integrity and synchronization between agents (JSON Schemas). |
| **System 1** | Implementation | **Governed Trader (Executor)** | The "Dumb Executor". Performs the actual value-generating operations (Trades). |

---

## 2. The MACAW Sequential Architecture

We implement a strict **Sequential Blocking Architecture** for high-risk operations, prioritizing **Safety over Latency**.

```mermaid
graph TD
    User --> Supervisor
    Supervisor -->|Intent: Trade| Planner[Execution Analyst]

    subgraph "System 4: Feedforward"
        Planner -->|Proposed Plan| Evaluator
    end

    subgraph "System 3: Control & Simulation"
        Evaluator -->|Parallel Check| M[Market Sim]
        Evaluator -->|Parallel Check| O[OPA Policy]
        Evaluator -->|Parallel Check| N[NeMo Semantics]

        M & O & N -->|Results| Evaluator
    end

    Evaluator -->|REJECTED| Planner
    Evaluator -->|APPROVED| Executor[Governed Trader]

    subgraph "System 1: Implementation"
        Executor -->|Execute Trade| API[Exchange API]
    end

    Executor --> Explainer

    subgraph "System 3: Monitoring"
        Explainer -->|Faithfulness Check| User
    end
```

### 2.1. Optimistic Planning, Pessimistic Execution

To balance User Experience (Latency) with Corporate Safety, we use a hybrid strategy:

1.  **Optimistic Speed (Internal):** The `Evaluator Node` runs its expensive checks (Market, OPA, NeMo) **in parallel** using `asyncio.gather`. This minimizes the wait time during the simulation phase.
2.  **Pessimistic Execution (Blocking):** The system **BLOCKS** the `Executor` until the Evaluator explicitly approves. There is no "Rollback" logic because financial trades are immutable. We verify *before* we act.

---

## 3. Infrastructure & vLLM Integration

The system employs a **Hybrid Inference Stack** to balance reasoning capability with latency and data sovereignty.

### 3.1. The Hybrid Client
The `HybridClient` (`src/governed_financial_advisor/infrastructure/llm_client.py`) routes traffic between two paths:

1.  **Reliable Path (Vertex AI Gemini):**
    *   **Use Case:** High-order reasoning, Planning (System 4), and Evaluation (System 3).
    *   **Model:** `gemini-2.5-pro` (Reasoning).
    *   **Why:** Requires maximum context window and reasoning depth.

2.  **Fast Path (Self-Hosted vLLM):**
    *   **Use Case:** Strict Schema Enforcement (JSON), Executor actions (System 1), and Latency-Critical Checks.
    *   **Model:** `meta-llama/Llama-3.1-8B-Instruct` (Hosted on GKE with NVIDIA L4).
    *   **Role in MACAW:**
        *   Used by the **Executor** and **Evaluator** for deterministic tasks.
        *   Enforces JSON schemas via `guided_json` (FSM), ensuring the "Dumb Executor" never hallucinates malformed tool calls.
        *   **Data Sovereignty:** Keeps sensitive execution details within the VPC/Cluster perimeter.

---

## 4. Governance Components

### 4.1. The Planner (Execution Analyst)
*   **Role:** Decomposes user intent into a DAG (Directed Acyclic Graph) of steps.
*   **Governance:** Fine-tuned on OpenAPI schemas to prevent "Tool Hallucination".

### 4.2. The Evaluator (The Critic)
*   **Role:** Simulates the plan against reality.
*   **Checks:**
    *   **Feasibility:** Is the market open? Do funds exist?
    *   **Regulatory:** Does this violate OPA policy?
    *   **Semantic:** Is this a jailbreak attempt (NeMo)?
*   **Cybernetics:** Provides the **Negative Feedback** loop to correct the Planner.

### 4.3. The Executor (Governed Trader)
*   **Role:** Pure implementation.
*   **Constraint:** "Dumb" agent. Cannot plan, cannot strategize. Only executes approved steps.

### 4.4. The Explainer
*   **Role:** Translates technical JSON into natural language.
*   **Governance:** Performs a **Faithfulness Check** (Self-Reflection) to ensure the explanation matches the execution logs, preventing "Post-Hoc Rationalization".

---

## 5. ISO 42001 Alignment

*   **Clause 6.1 (Actions to address risks):** The **Planner/Evaluator** loop functions as a dynamic Risk Assessment for every transaction.
*   **Clause 8.1 (Operational Planning):** The **Graph State** and **Evaluator Logic** constitute the operational controls.
*   **Clause 9.1 (Monitoring):** The **Explainer** and **Tracing (Langfuse)** provide real-time monitoring of agent performance.
>>>>>>> origin/docs/agentic-gateway-analysis-15132879769016669359
