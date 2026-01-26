# Architecture: Hybrid LangGraph + Google ADK + Hybrid Inference

This document describes the hybrid architecture of the Cybernetic Governance Engine, which combines **LangGraph** for deterministic workflow orchestration with **Google ADK** for LLM-powered agent reasoning, supported by a **Hybrid Inference Stack** (vLLM + Vertex AI).

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
├─────────────────────────────────────────────────────────────────────────────┤
│                          CAUSAL PLANE (System 2 Fallback)                   │
│  ┌───────────────────────┐                                                   │
│  │     Causal Engine     │ (Embedded Python Module)                          │
│  │  (ProductionSCM.pkl)  │                                                   │
│  └───────────────────────┘                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Why Hybrid?

| Concern | LangGraph | Google ADK |
|---------|-----------|------------|
| **Workflow Control** | ✅ Deterministic state machine | ❌ Probabilistic tool calls |
| **LLM Reasoning** | ❌ Manual prompt chaining | ✅ Native agent patterns |
| **Observability** | ✅ Explicit graph tracing | ✅ Built-in telemetry |
| **Checkpointing** | ✅ Redis/memory savers | ✅ Session service |

**The Insight**: Use LangGraph for what it does best (deterministic control flow, conditional routing, loops) and ADK for what it does best (LLM-powered reasoning, tool use, multi-turn conversations).

## Hybrid Inference Strategy (Latency as Currency)

To fund the "Governance Budget" (overhead of NeMo/OPA checks), we utilize a self-hosted high-performance inference stack.

*   **Fast Path:** **vLLM** on Kubernetes (GKE) with NVIDIA H100 GPUs.
    *   **Model:** `google/gemma-3-27b-it` (Target) + `google/gemma-3-4b-it` (Draft).
    *   **Technique:** Speculative Decoding (FP8).
    *   **SLA:** Time-To-First-Token (TTFT) < 200ms.
*   **Reliable Path:** **Vertex AI** (Gemini 2.5 Pro).
    *   **Fallback:** Triggered on connection error or SLA violation.

See [docs/LATENCY_STRATEGY.md](docs/LATENCY_STRATEGY.md) for details.

---

## Request Flow

```mermaid
sequenceDiagram
    participant User
    participant Server as FastAPI Server
    participant NeMo as NeMo Guardrails
    participant Graph as LangGraph StateGraph
    participant Supervisor as Supervisor Node
    participant Adapter as ADK Adapter
    participant Agent as ADK LlmAgent
    participant HybridClient as Hybrid LLM Client
    participant vLLM as Self-Hosted Inference
    participant Vertex as Vertex AI

    User->>Server: POST /agent/query
    Server->>NeMo: Validate input
    NeMo-->>Server: ✅ Safe
    Server->>Graph: graph.ainvoke()
    
    Graph->>Supervisor: Entry Point
    Supervisor->>Adapter: run_adk_agent(root_agent)
    Adapter->>Agent: Runner.run()
    Agent->>HybridClient: generate()

    alt Fast Path (vLLM)
        HybridClient->>vLLM: Stream Request
        vLLM-->>HybridClient: First Token (<200ms)
        vLLM-->>HybridClient: Full Response
    else Slow/Error
        HybridClient->>Vertex: Fallback Request
        Vertex-->>HybridClient: Response
    end

    Agent-->>Adapter: Response + route_request tool call
    Adapter-->>Supervisor: AgentResponse
    
    Note over Supervisor: Intercepts tool call<br/>to determine routing
    
    Supervisor-->>Graph: {next_step: "data_analyst"}
    Graph->>Adapter: data_analyst_node()
    Adapter->>Agent: Runner.run(data_analyst)
    Agent-->>Adapter: Analysis result
    Adapter-->>Graph: {messages: [...]}
    
    Graph-->>Server: Final state
    Server-->>User: JSON response
```

## Causal Fallback Flow (System 2)

When **OPA** returns `UNCERTAIN` for an action (e.g., blocking a high-tenure user), the request is routed to the embedded **Causal Engine**.

```mermaid
graph TD
    A[Optimistic Execution] -->|Action + Context| B{OPA Policy}
    B -->|ALLOW| C[Execute Action]
    B -->|DENY| D[Block Action]
    B -->|UNCERTAIN| E[System 2: Causal Engine]
    E -->|Simulate Intervention| F{Risk > Threshold?}
    F -->|Yes| D
    F -->|No| C
```

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
