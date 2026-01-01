# Cybernetic Governance of Agentic AI

This repository implements the **Cybernetic Governance** framework, transforming the Financial Advisor agent from a probabilistic LLM application into a deterministic, engineering-controlled system.

## 1. Theoretical Framework: HD-MDP
We utilize a **Hierarchical Deterministic Markov Decision Process (HD-MDP)** to solve the "Recursive Paradox" of agent safety (High Variety vs. Low Safety).

*   **Variety Attenuation:** We use Ashby's Law ($V_R \ge V_A$) to constrain the agent's infinite action space ($V_A$) into a manageable set of states verified by our governance stack ($V_R$).
*   **Explicit Routing:** Unlike standard "tool-use" agents that probabilistically choose tools, our **Supervisor Agent** uses a deterministic `route_request` tool to transition between states (Market Analysis -> Trading -> Risk). This forms the "hard logic" cage around the probabilistic "soft logic" of the LLM.

## 2. The Dynamic Risk-Adaptive Stack

The architecture enforces "Defense in Depth" through three distinct layers:

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
1.  **ALLOW:** Action proceeds automatically.
2.  **DENY:** Action is hard-blocked.
3.  **MANUAL_REVIEW:** Action is suspended pending human intervention ("Constructive Friction").

**Role-Based Access Control (RBAC):**
*   **Junior Trader:** Limit $5,000. Manual Review $5,000 - $10,000.
*   **Senior Trader:** Limit $500,000. Manual Review $500,000 - $1,000,000.
*   **Implementation:** `governance_poc/finance_policy.rego`

### Layer 3: The Semantic Verifier (Intent)
**Goal:** Semantic Safety & Anti-Hallucination.
A dedicated **Verifier Agent** audits the proposed actions of the "Worker" agent.
*   **Output:** A structured `RiskPacket` (JSON) containing:
    *   `risk_score` (1-100)
    *   `flags` (List of detected risks)
    *   `decision` (APPROVE, REJECT, ESCALATE)
*   **Implementation:** `financial_advisor/sub_agents/governed_trader/verifier.py`

## 3. Implementation Details

### The HD-MDP Router
The `financial_coordinator` agent does **not** have direct access to sub-agents. It cannot "hallucinate" a call to `governed_trading_agent`.
Instead, it MUST use the `route_request` tool (`financial_advisor/tools/router.py`), which executes a deterministic `transfer_to_agent` call based on a strict `RouterIntent` Enum.

### Governance Decorator
The `@governed_tool` decorator (`financial_advisor/governance.py`) intercepts all tool executions.
1.  Validates Pydantic Schema (Layer 1).
2.  Queries OPA Sidecar (Layer 2).
3.  If OPA returns `MANUAL_REVIEW`, it returns a `PENDING_HUMAN_REVIEW` signal to the agent, halting execution.

## 4. Local Development

### Prerequisites
*   [Open Policy Agent (OPA)](https://www.openpolicyagent.org/docs/latest/#running-opa) installed.

### Running the Stack
1.  **Start OPA Server:**
    ```bash
    ./opa run -s -b . --addr :8181
    ```
2.  **Run Tests:**
    ```bash
    uv run pytest tests/verify_full_stack.py
    ```

## 5. Deployment (Cloud Run Sidecar)

The architecture is designed for Google Cloud Run with OPA as a sidecar container.
*   **Application Container:** Python/FastAPI agent.
*   **Sidecar Container:** OPA serving the Rego policy.
*   **Communication:** Localhost HTTP (Application -> `localhost:8181` -> OPA).
