# Gap Analysis Report: Green Stack Governance Architecture

## Executive Summary
The repository implements a **high-maturity version** of the "Green Stack" architecture described in the specification. The core Cybernetic Control Loop, Governance Transpiler, and Safety Interceptor patterns are present and functional.

However, a significant **architectural divergence** exists: the repository implements a "Hybrid" model (LangGraph + Google ADK with Adapters) rather than the pure LangGraph/NeMo model implied by the text. Additionally, the "Risk Analyst" agent has been moved from the runtime loop to an offline/asynchronous role, replaced by a deterministic "Safety Node" and "Consensus Engine" for runtime enforcement.

## 1. Terminology Map

| Specification Term | Repository Implementation | Notes |
| :--- | :--- | :--- |
| **Green Stack** | `src/governance/`, `src/graph/nodes/safety_node.py` | The entire safety architecture. |
| **Controller** | `src/graph/graph.py` + `src/nodes/supervisor_node.py` | Hybrid: LangGraph handles routing, Google ADK handles reasoning. |
| **Actuators** | `src/agents/*/tools/` | Tools called by agents. |
| **Sensors** | `src/infrastructure/telemetry/` | OpenTelemetry implementation. |
| **Green Agent** | `src/agents/risk_analyst/` (Offline) + `src/governance/safety.py` (Runtime) | Split into "Offline Analysis" and "Runtime Enforcement". |
| **Purple Agent** | `src/agents/governed_trader/` | The functional agent attempting actions. |
| **Policy Transpiler**| `src/governance/transpiler.py` | Automated STPA -> Rego/Colang converter. |
| **Safety Interceptor**| `src/graph/nodes/safety_node.py` | Explicit node in the graph. |
| **Consensus Engine** | `src/governance/consensus.py` | Multi-Agent Debate implementation. |

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

*   **Sidecar Deployment Config:** While `client.py` supports connecting to an OPA URL, there are no visible `Dockerfile` or `kubernetes.yaml` files in the source tree that *actually deploy* OPA as a sidecar. The implementation assumes the infrastructure exists.
*   **Green Agent Entry Point:** There is no `src/green_agent/` directory, despite the terminology. The logic is distributed across `src/governance/` and `src/agents/risk_analyst/`.

## 5. Conclusion
The repository is a **faithful and advanced implementation** of the "Green Stack" philosophy. It deviates primarily in *how* it achieves the goals (using a Hybrid ADK/LangGraph architecture and "Offline" Risk Analyst), but it fulfills the functional safety requirements (CBFs, Consensus, Policy Transpilation, Auditability) with high fidelity.
