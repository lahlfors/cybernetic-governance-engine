# Cybernetic Governance of Agentic AI

This repository implements the **Cybernetic Governance** framework, transforming the Financial Advisor agent from a probabilistic LLM application into a deterministic, engineering-controlled system.

## 1. Theoretical Framework: Hybrid Reasoning Architecture & STPA
We utilize a **Hybrid Reasoning Architecture** to solve the "Recursive Paradox" of agent safety (High Variety vs. Low Safety). This architecture combines **deterministic workflow control** (LangGraph) with **LLM-powered reasoning** (Google ADK).
We also employ **Systems-Theoretic Process Analysis (STPA)** to identify and mitigate Unsafe Control Actions (UCAs). See [STPA_ANALYSIS.md](STPA_ANALYSIS.md) for the detailed hazard analysis.

*   **Variety Attenuation:** We use Ashby's Law ($V_R \ge V_A$) to constrain the agent's infinite action space ($V_A$) into a manageable set of states verified by our governance stack ($V_R$).
*   **Explicit Routing (LangGraph):** Unlike standard "tool-use" agents that probabilistically choose tools, our **Supervisor Agent** (implemented in **LangGraph**) uses a deterministic State Graph to transition between states (Market Analysis -> Trading -> Risk). This forms the "hard logic" cage around the probabilistic "soft logic" of the LLM.

## 2. The Dynamic Risk-Adaptive Stack

The architecture enforces "Defense in Depth" through six distinct layers (0-5):

### Layer 0: Conversational Guardrails (NeMo)
**Goal:** Input/Output Safety & Topical Control.
We use **NeMo Guardrails** running **In-Process** as the first line of defense to ensure the model stays on topic and avoids jailbreaks *before* it even processes a tool call. The in-process architecture is validated in both the main `server.py` entry point and the parallel safety checks in `optimistic_nodes.py`.
*   **Implementation:** `src/utils/nemo_manager.py` & `config/rails/`
*   **Observability (ISO 42001):** A custom `NeMoOTelCallback` intercepts every guardrail intervention (e.g., `self_check_input`) and emits an OpenTelemetry span with `guardrail.outcome` and `iso.control_id="A.6.2.8"`.

### Layer 1: Session Persistence (Redis)
**Goal:** Stateful Sessions on Stateless Compute.
Cloud Run containers are **stateless** (ephemeral). To maintain session continuity, we use **Redis (Cloud Memorystore)** for session state persistence.
*   **Constraint:** Session state is checkpointed to Redis after each turn.
*   **Safety:** This ensures consistent behavior even if the compute node was destroyed and recreated.
*   **Implementation:** `src/graph/checkpointer.py` using Redis-backed session storage.

### Layer 2: The Syntax Trapdoor (Schema)
**Goal:** Structural Integrity.
We use strict **Pydantic** models to validate every tool call *before* it reaches the policy engine.
*   **Implementation:** `src/tools/trades.py`
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
*   **Implementation:** `src/governance/policy/finance_policy.rego`

**State Management (CBF):**
The `ControlBarrierFunction` in `safety.py` now supports transactional state updates with `rollback_state(cost)` to handle failed downstream executions.

### Layer 4: The Semantic Verifier (Intent)
**Goal:** Semantic Safety & Anti-Hallucination.
We implement a **Propose-Verify-Execute** pattern:
1.  **Worker Agent:** Uses `propose_trade` to draft an action. It *cannot* execute trades.
2.  **Verifier Agent:** Audits the proposal against the prompt and safety rules.
    *   **Tool:** `submit_risk_assessment`. Enforces a structured `RiskPacket` schema (Risk Score, Flags, Decision).
    *   **Execution:** Only the Verifier can call `execute_trade`.
*   **Implementation:** `src/agents/governed_trader/agent.py` (Verifier logic)

### Layer 5: The Consensus Engine (Adaptive Compute)
**Goal:** High-Stakes Validation.
For actions exceeding a high-risk threshold ($10,000), the system triggers an **Ensemble Check**.
*   **Mechanism:** The `ConsensusEngine` orchestrates a multi-agent debate (using distinct "Risk Manager" and "Compliance Officer" personas) to ensure unanimous agreement before execution.
*   **Model Configuration:** Uses `MODEL_CONSENSUS` environment variable (defaults to `MODEL_REASONING`).
*   **Integration:** Embedded in the `@governed_tool` decorator. If the consensus check fails, the trade is blocked even if OPA approves.
*   **Implementation:** `src/governance/consensus.py`

### Layer 6: Human-in-the-Loop (Escalation)
**Goal:** The Grey Zone & Constructive Friction.
When the Consensus Engine encounters ambiguous scenarios (e.g., complex life events, borderline risk), it returns an `ESCALATE` vote instead of a hard `REJECT`.
*   **Mechanism:** The system halts execution and returns a `MANUAL_REVIEW` status.
*   **Concept:** This implements "Escalation as a Fallback," ensuring that the automated system has a fail-safe path to human judgment for "Grey Zone" decisions.
*   **Implementation:** `src/governance/consensus.py` (Vote Logic) & `src/governance/client.py` (Routing).

## 3. Tiered Observability: The Cost of Transparency
We implement a **Risk-Based Tiered Strategy** for observability, solving the paradox of "Logging everything vs. Paying for everything."

### The Dilemma
*   **Hot Storage (Datadog/Cloud Trace):** Essential for operational health (latency, error rates) but prohibitively expensive for storing full LLM payloads (prompts/responses).
*   **Cold Storage (S3/GCS):** Cheap but slow to query. Essential for compliance and forensics ("Why did the agent do that?").

### The Solution: Tiered Observability (Implemented)
The architecture implements a **GenAICostOptimizerProcessor** that routes spans to different tiers:
*   **Implementation:** `src/infrastructure/telemetry/processors/genai_cost_optimizer.py`
*   **Cold Tier Exporter:** `ParquetSpanExporter` writes full-fidelity spans to GCS with date partitions

| Tier | Destination | Content | Sampling Logic | Purpose |
|------|-------------|---------|----------------|---------|
| **Hot** | Cloud Trace / Langfuse | Metadata Only (Latency, Status, TraceID) | 100% | Operational Health |
| **Cold** | GCS Parquet (`gs://bucket/cold_tier/YYYY/MM/DD/`) | Full Payload (Prompts, Reasoning, RAG Chunks) | **Smart Sampled** | Forensics & Compliance |

> **Configuration:** Set `COLD_TIER_GCS_BUCKET` env var to enable GCS. Falls back to local disk if not configured.

## 4. Implementation Details

### The Deterministic Router (LangGraph)
The `financial_coordinator` (Supervisor) does **not** have direct access to sub-agents. It cannot "hallucinate" a call to `governed_trading_agent`.
Instead, we use **LangGraph** to implement a rigid State Graph that separates control from reasoning.
*   **Supervisor Node:** Routes user intents to specific agent nodes (Data, Execution, Governed Trader).
*   **Risk Refinement Loop:** If the **Optimistic Execution Node** (Safety Layer) detects a violation, the graph *automatically* routes back to the Execution Analyst. The system injects the specific risk feedback into the prompt, forcing the planner to self-correct before the trade can proceed. This ensures that no unsafe plan can reach the Execution state.

### Governance Decorator
The `@governed_tool` decorator (`src/governance/client.py`) intercepts all tool executions.
1.  Validates Pydantic Schema (Layer 1).
2.  Queries OPA Sidecar (Layer 2).
3.  Triggers Consensus Engine if applicable (Layer 4).
4.  Wraps execution in GenAI Telemetry spans.

## 5. Local Development

### Prerequisites
*   [Open Policy Agent (OPA)](https://www.openpolicyagent.org/docs/latest/#running-opa) installed.

### Running the Stack
1.  **Start OPA Server:**
    ```bash
    ./opa run -s -b . --addr :8181
    ```
2.  **Run Tests:**
    ```bash
    uv run python3 -m unittest discover tests
    ```

## 6. Deployment (Cloud Run Sidecar)

The architecture is designed for Google Cloud Run with OPA as a sidecar container.
*   **Application Container:** Python/FastAPI agent.
*   **Sidecar Container:** OPA serving the Rego policy.
*   **Communication:** Localhost HTTP (Application -> `localhost:8181` -> OPA).

For detailed deployment instructions, including the sidecar configuration and startup checks, please see **[deployment/README.md](deployment/README.md)**.
