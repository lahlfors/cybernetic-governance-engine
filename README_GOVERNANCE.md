# Cybernetic Governance of Agentic AI

This repository implements the **Cybernetic Governance** framework, transforming the Financial Advisor agent from a probabilistic LLM application into a deterministic, engineering-controlled system.

## 1. Theoretical Framework: HD-MDP & STPA
We utilize a **Hierarchical Deterministic Markov Decision Process (HD-MDP)** to solve the "Recursive Paradox" of agent safety (High Variety vs. Low Safety).
We also employ **Systems-Theoretic Process Analysis (STPA)** to identify and mitigate Unsafe Control Actions (UCAs). See [STPA_ANALYSIS.md](STPA_ANALYSIS.md) for the detailed hazard analysis.

*   **Variety Attenuation:** We use Ashby's Law ($V_R \ge V_A$) to constrain the agent's infinite action space ($V_A$) into a manageable set of states verified by our governance stack ($V_R$).
*   **Explicit Routing:** Unlike standard "tool-use" agents that probabilistically choose tools, our **Supervisor Agent** uses a deterministic `route_request` tool to transition between states (Market Analysis -> Trading -> Risk). This forms the "hard logic" cage around the probabilistic "soft logic" of the LLM.

## 2. The Dynamic Risk-Adaptive Stack

The architecture enforces "Defense in Depth" through six distinct layers (0-5):

### Layer 0: Conversational Guardrails (NeMo)
**Goal:** Input/Output Safety & Topical Control.
We use **NeMo Guardrails** as the first line of defense to ensure the model stays on topic and avoids jailbreaks *before* it even processes a tool call.
*   **Implementation:** `financial_advisor/nemo_manager.py` & `financial_advisor/rails_config/`
*   **Features:**
    *   **Input Rails:** Detect jailbreak attempts or off-topic queries.
    *   **Output Rails:** Ensure the tone and content match the financial advisor persona.
    *   **Topical Rails:** Restrict conversation to financial domains.

### Layer 1: The Syntax Trapdoor (Schema)
**Goal:** Structural Integrity.
We use strict **Pydantic** models to validate every tool call *before* it reaches the policy engine.
*   **Implementation:** `financial_advisor/tools/trades.py`
*   **Features:**
    *   **UUID Validation:** `transaction_id` must be a valid UUID v4.
    *   **Regex Validation:** Ticker symbols must match `^[A-Z]{1,5}$`.
    *   **Role Context:** `trader_role` (Junior/Senior) is enforced in the schema.

### Layer 2: The Policy Engine (RBAC & OPA)
**Goal:** Authorization & Business Logic.
We use **Open Policy Agent (OPA)** and **Rego** to decouple policy from code. The system implements a **Tri-State Decision** logic:
1.  **ALLOW:** Action proceeds to next layer.
2.  **DENY:** Action is hard-blocked.
3.  **MANUAL_REVIEW:** Action is suspended pending human intervention ("Constructive Friction").

**Role-Based Access Control (RBAC):**
*   **Junior Trader:** Limit $5,000. Manual Review $5,000 - $10,000.
*   **Senior Trader:** Limit $500,000. Manual Review $500,000 - $1,000,000.
*   **Implementation:** `governance_poc/finance_policy.rego`

### Layer 3: The Semantic Verifier (Intent)
**Goal:** Semantic Safety & Anti-Hallucination.
We implement a **Propose-Verify-Execute** pattern:
1.  **Worker Agent:** Uses `propose_trade` to draft an action. It *cannot* execute trades.
2.  **Verifier Agent:** Audits the proposal against the prompt and safety rules.
    *   **Tool:** `submit_risk_assessment`. Enforces a structured `RiskPacket` schema (Risk Score, Flags, Decision).
    *   **Execution:** Only the Verifier can call `execute_trade`.
*   **Implementation:** `financial_advisor/sub_agents/governed_trader/verifier.py`

### Layer 4: The Consensus Engine (Adaptive Compute)
**Goal:** High-Stakes Validation.
For actions exceeding a high-risk threshold ($10,000), the system triggers an **Ensemble Check**.
*   **Mechanism:** The `ConsensusEngine` simulates a voting process (mocked for this sample) to ensure unanimous agreement before execution.
*   **Integration:** Embedded in the `@governed_tool` decorator. If the consensus check fails, the trade is blocked even if OPA approves.
*   **Implementation:** `financial_advisor/consensus.py`

### Layer 5: Human-in-the-Loop (Escalation)
**Goal:** The Grey Zone & Constructive Friction.
When the Consensus Engine encounters ambiguous scenarios (e.g., complex life events, borderline risk), it returns an `ESCALATE` vote instead of a hard `REJECT`.
*   **Mechanism:** The system halts execution and returns a `MANUAL_REVIEW` status.
*   **Concept:** This implements "Escalation as a Fallback," ensuring that the automated system has a fail-safe path to human judgment for "Grey Zone" decisions.
*   **Implementation:** `financial_advisor/consensus.py` (Vote Logic) & `financial_advisor/governance.py` (Routing).

## 3. Observability: GenAI Semantics
We implement **OpenTelemetry** with **GenAI Semantic Conventions** (v1.37+ draft) to ensure full visibility into the "Black Box" of cognition.
*   **Attributes:** Captures `gen_ai.content.prompt`, `gen_ai.content.completion`, and `gen_ai.tool.name`.
*   **Spans:** Each cognitive step (Reasoning, Tool Use, Consensus Check) is a distinct span in the trace.
*   **Implementation:** `financial_advisor/telemetry.py`

## 4. Implementation Details

### The HD-MDP Router
The `financial_coordinator` agent does **not** have direct access to sub-agents. It cannot "hallucinate" a call to `governed_trading_agent`.
Instead, it MUST use the `route_request` tool (`financial_advisor/tools/router.py`), which executes a deterministic `transfer_to_agent` call based on a strict `RouterIntent` Enum.

### Governance Decorator
The `@governed_tool` decorator (`financial_advisor/governance.py`) intercepts all tool executions.
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
