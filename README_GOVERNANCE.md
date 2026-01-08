# Cybernetic Governance of Agentic AI

This repository implements the **Cybernetic Governance** framework, transforming the Financial Advisor agent from a probabilistic LLM application into a deterministic, engineering-controlled system.

## 1. Philosophy: Governance is not a Prompt. It’s an Architecture. 🏛️

In the rush to deploy Agentic AI, we often confuse "Instruction" with "Control." You can *instruct* an LLM to be safe via a System Prompt, but you can only *control* it via Architecture.

This distinction is the heart of Agentic Governance.

For high-stakes domains (Finance, Healthcare, Legal), the industry is converging on the **HD-MDP (Hierarchical Deterministic Markov Decision Process)** as the standard for safety.

**What is an HD-MDP?** It’s a fancy term for a simple safety philosophy:
*   **Hierarchical:** High-level policy manages low-level execution.
*   **Deterministic:** Transitions between states (e.g., from "Drafting" to "Publishing") are hard-coded logic gates, not LLM choices.
*   **Markovian:** The agent's next move depends on its verified state, not just its chat history.

To build an HD-MDP, you need to choose your Control Structure. We compared Google ADK vs. LangGraph.

### 1. Google ADK Workflow Agents (The Assembly Line)
The ADK uses a Directed Acyclic Graph (DAG).
*   **The Governance Model:** Linear Compliance.
*   **How it works:** It excels at "Straight-Through Processing." You feed input A, it passes through Tools B and C, and produces Output D.
*   **The Limitation:** It struggles with the "Markov" aspect. If a risk check fails at Step C, the architecture fights you. It wants to finish the flow, not loop back to Step A for a correction. It is Task-Centric.

### 2. LangGraph (The Governance Loop)
LangGraph uses a Cyclic State Graph (FSM).
*   **The Governance Model:** Recursive Correction.
*   **How it works:** Nodes can point backwards. If the "Risk Auditor" node rejects a plan, the graph deterministically routes the agent back to the "Planner" node with error feedback.
*   **The Advantage:** This perfectly mirrors the HD-MDP pattern. You can mathematically prove that the agent cannot reach the "Execution" node without traversing the "Compliance" node. It is State-Centric.

### The Architect's Verdict
*   If you are building **Capabilities** (e.g., "Summarize this PDF"), use ADK. Its linear efficiency is unmatched.
*   If you are building **Governance** (e.g., "Execute this Trade safely"), use LangGraph. You need the cycles to enforce the HD-MDP safety guarantees.

**Stop hoping your agents will behave. Start architecting them so they have no choice.**

## 2. Theoretical Framework: HD-MDP & STPA
We utilize the HD-MDP to solve the "Recursive Paradox" of agent safety (High Variety vs. Low Safety).
We also employ **Systems-Theoretic Process Analysis (STPA)** to identify and mitigate Unsafe Control Actions (UCAs). See [STPA_ANALYSIS.md](STPA_ANALYSIS.md) for the detailed hazard analysis.

*   **Variety Attenuation:** We use Ashby's Law ($V_R \ge V_A$) to constrain the agent's infinite action space ($V_A$) into a manageable set of states verified by our governance stack ($V_R$).
*   **Explicit Routing:** We use **LangGraph** to enforce the strict state machine (Analysis -> Strategy -> Risk -> Execution). This forms the "hard logic" cage around the probabilistic "soft logic" of the LLM.

## 3. The Dynamic Risk-Adaptive Stack

The architecture enforces "Defense in Depth" through six distinct layers (0-5):

### Layer 0: Conversational Guardrails (NeMo)
**Goal:** Input/Output Safety & Topical Control.
We use **NeMo Guardrails** as the first line of defense to ensure the model stays on topic and avoids jailbreaks *before* it even processes a tool call.
*   **Implementation:** `financial_advisor/server.py` & `financial_advisor/rails_config/`

### Layer 1: The Cognitive Bridge (Redis State)
**Goal:** Long-Term Context & KYC Compliance.
Cloud Run containers are **stateless** (ephemeral). To provide reliable advice, we use **Redis (Cloud Memorystore)** as a persistent state layer.
*   **Constraint:** The agent accesses user history and conversation state via **LangGraph Checkpointing** at the start of every session.
*   **Safety:** This ensures consistent advice ("Don't suggest Oil stocks") even if the compute node was destroyed and recreated 5 seconds ago.
*   **Implementation:** `financial_advisor/graph.py` (RedisSaver).

### Layer 2: The Syntax Trapdoor (Schema)
**Goal:** Structural Integrity.
We use strict **Pydantic** models to validate every tool call *before* it reaches the policy engine.
*   **Implementation:** `financial_advisor/tools/trades.py`
*   **Features:**
    *   **UUID Validation:** `transaction_id` must be a valid UUID v4.
    *   **Regex Validation:** Ticker symbols must match `^[A-Z]{1,5}$`.
    *   **Role Context:** `trader_role` (Junior/Senior) is enforced in the schema.

### Layer 3: The Policy Engine (RBAC & OPA)
**Goal:** Authorization & Business Logic.
We use **Open Policy Agent (OPA)** and **Rego** to decouple policy from code. The system implements a **Tri-State Decision** logic:
1.  **ALLOW:** Action proceeds to next layer.
2.  **DENY:** Action is hard-blocked.
3.  **MANUAL_REVIEW:** Action is suspended pending human intervention ("Constructive Friction").

**Role-Based Access Control (RBAC):**
*   **Junior Trader:** Limit $5,000. Manual Review $5,000 - $10,000.
*   **Senior Trader:** Limit $500,000. Manual Review $500,000 - $1,000,000.
*   **Architecture (Sidecar):** OPA runs as a sidecar container on `localhost`. This eliminates network latency, enabling **real-time** compliance checks critical for high-frequency trading decisions.
*   **Implementation:** `governance_poc/finance_policy.rego`

### Layer 4: The Deterministic Flow (Logic)
**Goal:** Semantic Safety & Anti-Hallucination.
We implement a **Deterministic Flow** for critical tasks:
1.  **Market Analyst:** Uses `google_search_tool` via code invocation (not LLM choice) to prevent hallucinated tool calls.
2.  **Governed Trader:** Cannot execute unless the OPA Policy Check passes (Hard Gate in the Graph Node).
*   **Implementation:** `financial_advisor/nodes.py`

### Layer 5: Observability (OpenTelemetry)
**Goal:** Transparent Audit Trail.
We implement **OpenTelemetry** with **OpenInference** to ensure full visibility into the "Black Box" of cognition.
*   **Attributes:** Captures ISO controls (`iso.control_id`), sensitivity, and outcomes.
*   **Spans:** Each cognitive step (Analysis, Strategy, Risk, Trading) is a distinct span in the trace.
*   **Implementation:** `financial_advisor/telemetry.py`

## 4. Implementation Details

### The HD-MDP Graph
The system is defined as a `StateGraph` in `financial_advisor/graph.py`.
*   **Transitions:** The edges define the strict path: `market_analysis` -> `trading_strategy` -> `risk_assessment` -> `governed_trading`.
*   **State:** The `AgentState` strictly defines the artifacts required at each step.

### Deterministic Nodes
In `financial_advisor/nodes.py`, we replace probabilistic agents with deterministic functions where possible.
*   **Market Analysis:** `google_search_tool.invoke(query)` is called directly.
*   **Trading Node:** Calls `opa_client.check_policy()` explicitly before any trade execution.

## 5. Local Development

### Prerequisites
*   [Open Policy Agent (OPA)](https://www.openpolicyagent.org/docs/latest/#running-opa) installed.
*   Redis running locally.

### Running the Stack
1.  **Start OPA Server:**
    ```bash
    ./opa run -s -b . --addr :8181
    ```
2.  **Start Agent:**
    ```bash
    uv run uvicorn financial_advisor.server:app --port 8080 --reload
    ```

## 6. Deployment (Cloud Run Sidecar)

The architecture is designed for Google Cloud Run with OPA as a sidecar container.
*   **Application Container:** Python/FastAPI agent.
*   **Sidecar Container:** OPA serving the Rego policy.
*   **Communication:** Localhost HTTP (Application -> `localhost:8181` -> OPA).

For detailed deployment instructions, including the sidecar configuration and startup checks, please see **[deployment/README.md](deployment/README.md)**.
