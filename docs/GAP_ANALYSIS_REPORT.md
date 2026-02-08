# Gap Analysis Report: Green Stack Governance Architecture

## Executive Summary
The repository implements a **high-maturity version** of the "Green Stack" architecture described in the specification. The core Cybernetic Control Loop, Governance Transpiler, and Safety Interceptor patterns are present and functional.

However, a significant **architectural divergence** exists: the repository implements a "Hybrid" model (LangGraph + Google ADK with Adapters) rather than the pure LangGraph/NeMo model implied by the text. Additionally, the "Risk Analyst" agent has been moved from the runtime loop to an offline/asynchronous role, replaced by a deterministic "Safety Node" and "Consensus Engine" for runtime enforcement.

## 1. Terminology Deviation & Recommendation

The repository uses "Risk Analyst" and "Safety Node" instead of the abstract "Green Agent" terminology found in the specification.

**Recommendation:** The Specification should be updated to align with the Repository's precise terminology:
*   Replace **"Green Agent" (Discovery Phase)** with **"Risk Analyst"**.
*   Replace **"Green Agent" (Enforcement Phase)** with **"Safety Node"** and **"Governance Layer"**.
*   Retain **"Green Stack"** as the name for the overall architectural pattern.

## 2. Verified Implementation (Matches Specification)

### Governance & Policy
*   ✅ **Policy Transpiler:** `src/governance/transpiler.py` correctly implements the logic to convert `ProposedUCA` (Unsafe Control Actions) into both Python functions (for NeMo) and Rego policies (for OPA).
*   ✅ **Mathematical Safety (CBF):** `src/governance/safety.py` implements Control Barrier Functions with Redis-backed state persistence, enforcing the `h(next) >= (1-gamma) * h(current)` invariant.
*   ✅ **Consensus Engine:** `src/governance/consensus.py` implements the "Multi-Agent Debate" pattern (Risk Manager + Compliance Officer) for high-stakes transactions.

### Architecture & Control
*   ✅ **Safety Interceptor Pattern:** `src/graph/graph.py` explicitly routes execution through a `safety_check` node before the `governed_trader` can execute tools.
*   ✅ **Self-Healing Loop:** The graph includes a feedback edge from `safety_check` back to `execution_analyst` (Planner) upon rejection, allowing the agent to "try again" with a corrected plan.
*   ✅ **Human-in-the-Loop:** `interrupt_before=["human_review"]` is configured in the graph compilation.

### Observability
*   ✅ **Automated Auditor:** `scripts/automated_auditor.py` implements the logic to verify the invariant: "Every Execution span must be preceded by a Governance Check span."
*   ✅ **ISO 42001 Compliance:** Code in `src/server.py` and `src/governance/client.py` explicitly tags traces with `enduser.id`, `governance.decision`, and `consensus.votes`, matching the compliance documentation.

## 3. Discrepancies & Deviations

### A. Architectural Divergence (Hybrid Model)
*   **Spec:** Implies a unified "LangGraph Controller".
*   **Repo:** Implements a **Hybrid LangGraph + Google ADK** architecture.
    *   **Evidence:** `ARCHITECTURE.md` and `src/graph/nodes/adapters.py`.
    *   **Impact:** The system is more complex than described. It uses "Adapters" to bridge the deterministic LangGraph control plane with the probabilistic Google ADK reasoning plane. This is a *valid* engineering choice (often better for enterprise) but differs from the simplified text.

### B. Risk Analyst Placement
*   **Spec:** Implies the Risk Analyst is a "System 1 Worker" or active participant.
*   **Repo:** Explicitly removes the Risk Analyst from the hot path.
    *   **Evidence:** `src/graph/graph.py`: `# Risk Analyst is removed from hot path (runs offline)`.
    *   **Impact:** Runtime safety is handled by the *Safety Node* (deterministic rules) rather than the *Risk Analyst Agent* (LLM). This is likely an optimization for latency (System 2 vs System 1 thinking).

### C. NeMo Guardrails Scope
*   **Spec:** Mentions "Fact-Checking Rail" and "RAG Verification" as key features.
*   **Repo:** `config/rails/flows.co` focuses on **Financial Risk Checks** (Latency, Drawdown, Atomic Execution).
    *   **Evidence:** `flows.co` defines `check financial risk` but lacks explicit "check facts" or "check hallucination" flows.
    *   **Impact:** The specific "RAG Verification" feature mentioned in the text appears to be either missing or configured implicitly/defaults (not visible in custom flows).

## 4. Missing Features (Gap Analysis)

*   **Sidecar Deployment Config:** The implementation of the Sidecar pattern is fully realized in `deployment/service.yaml` (Knative/Cloud Run configuration) and orchestrated by `deployment/deploy_all.py`. This contradicts the initial gap finding; the infrastructure code is present but located in the `deployment/` directory rather than the root.
*   **Green Agent Entry Point:** There is no `src/green_agent/` directory, despite the terminology. The logic is distributed across `src/governance/` and `src/agents/risk_analyst/`.

## 5. Deep Dive Findings (Response to Specific Questions)

### A. Feedback Loop Mechanics & Race Conditions
*   **Mechanism:** The "Risk Analyst" (Offline) intervenes solely through **Policy Updates**. `scripts/offline_risk_update.py` directly overwrites `src/governance/generated_actions.py` and `src/governance/policy/generated_rules.rego`.
*   **Race Conditions:** The script uses direct file I/O (`open(..., 'w')`) without any version control integration (Git) or locking mechanisms. This creates a risk where concurrent runs could corrupt policy files, or updates could break the production build without review. There is **no PR-based workflow** implemented in the code.

### B. Scope of Financial Risk Checks
*   **Finding:** The runtime hot path is heavily optimized for **Deterministic Financial Safety** (Latency, Atomic Execution, Slippage, Drawdown, Authorization).
*   **Gap:** "Semantic Checks" (PII masking, advanced toxicity filters) are **implicit or minimal**. `config/rails/config.yml` enables standard `self check input` flows but does not configure specific PII scrubbing tools (like Presidio) or external toxicity classifiers in the custom actions list. The system prioritizes speed and financial correctness over content moderation in the custom layer.

### C. State Management & Multistep Risks
*   **Finding:** The `risk_analyst` agent is **Stateless** and **Ahistorical**.
*   **Evidence:** `src/agents/risk_analyst/agent.py` inputs are limited to `provided_trading_strategy`, `execution_plan_output`, and `user_risk_attitude`. It does not receive conversation history or past execution logs.
*   **Implication:** The agent acts as a **Plan Validator**, not a History Auditor. It cannot detect **"Salami Slicing"** or other temporal/cumulative risks (e.g., slow memory leaks, gradual bias drift) because it lacks the longitudinal context to see the pattern across multiple invocations.

### D. Policy Activation Latency
*   **Assessment:** High Latency.
*   **Reasoning:** Since updates involve overwriting source code (`.py`) and policy files (`.rego`), applying a new UCA requires a **Service Redeployment** (to rebuild the container with new code) or a complex hot-reload mechanism (not visible in `deployment/`).
*   **Time-to-Mitigation:** Likely minutes (CI/CD build time + Cloud Run deployment time). This is generally **unsuitable** for high-frequency trading environments where millisecond-level reaction to new threat vectors is required, unless the "Safety Node" has a separate dynamic configuration channel (which is implemented via Redis for CBF, but not for the transpiled logic).

## 6. Remediation Plan

To address the deep-dive findings (Latency, Statelessness, Race Conditions), a formal Remediation Proposal has been created.

👉 **See: [docs/proposals/004_risk_remediation_plan.md](docs/proposals/004_risk_remediation_plan.md)**

**Summary of Proposed Changes:**
1.  **Dynamic Policy Injection:** Switch OPA Sidecar to use **Bundle Polling** (hot-reload from GCS/S3) instead of local file mounts.
2.  **Stateful Risk Memory:** Implement a Redis-backed `RiskMemory` class to track temporal transaction patterns (Salami Slicing detection).
3.  **GitOps Workflow:** Refactor `offline_risk_update.py` to open **Pull Requests** rather than overwriting files directly.

## 7. Conclusion
The repository is a **faithful and advanced implementation** of the "Green Stack" philosophy. It deviates primarily in *how* it achieves the goals (using a Hybrid ADK/LangGraph architecture and "Offline" Risk Analyst), but it fulfills the functional safety requirements (CBFs, Consensus, Policy Transpilation, Auditability) with high fidelity.
