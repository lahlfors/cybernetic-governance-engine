# Changelog

All notable changes to this project will be documented in this file.

<<<<<<< HEAD
## [Unreleased]

### Added
- **TPU Deployment Support:** Added native support for deploying the inference stack to Google Cloud TPU v5e via `deploy_all.py` (flag `--accelerator tpu`).
    - **Analysis Report:** Added `docs/TPU_MIGRATION_ANALYSIS.md` detailing the cost-benefit analysis and feature gaps (e.g., Speculative Decoding) of migrating from H100 to TPU v5e.
    - **Dynamic Provisioning:** Deployment script now automatically provisions TPU v5e node pools (`ct5lp-hightpu-8t`) if they don't exist.
    - **Manifest Generation:** Refactored `vllm-deployment.yaml` to a template to support dynamic injection of hardware-specific vLLM args (XLA/Pallas for TPU vs CUDA for GPU).
- **Dynamic Control Barrier Function (CBF):** Implemented a hybrid safety architecture for the Drawdown Limit.
    - **Static Mechanism:** Hardcoded `check_drawdown_limit` in `nemo_actions.py` enforcing $h(x) = Limit - Value \ge 0$.
    - **Dynamic Policy:** Added `safety_params.json` support to allow the offline Risk Analyst to update safety thresholds without code deployment.
    - **Safety Hardening:** Implemented strict input sanitization, safe defaults (5%), and atomic file updates.
- **Red Teaming Tests:** Added `tests/test_red_teaming.py` to verify hot-reloading and resilience to corrupt configuration.
- **Transpiler Upgrade:** Updated `PolicyTranspiler` to extract safety parameters from identified UCAs.
=======
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Agentic Gateway (Microservice):** Introduced a new gRPC-based Sidecar Service (`src/gateway/`) to centralize infrastructure and governance.
- **Execution Proxy Pattern:** Agents now delegate sensitive operations (`execute_trade`) to the Gateway via RPC. The Gateway enforces OPA policies, Safety Filters, and Consensus *before* execution.
- **LLM Proxy:** `HybridClient` now routes all generation requests through the Gateway for centralized observability (token counting, cost tracking).
- **Documentation:** Added `docs/AGENTIC_GATEWAY_ANALYSIS.md` detailing the architectural shift.

### Changed
- **Refactored `HybridClient`:** The agent-side client (`infrastructure/llm_client.py`) is now a thin gRPC stub. Logic moved to `src/gateway/core/llm.py`.
- **Refactored `execute_trade`:** The tool function (`tools/trades.py`) is now an async wrapper calling `gateway_client.execute_tool`.
- **Deprecated Local Governance:** `OPAClient` and `CircuitBreaker` in `governance/client.py` are deprecated. All policy enforcement happens in the Gateway.

### Removed
- **`@governed_tool` Decorator:** Removed local decorator usage from `execute_trade`. Governance is now a service-level concern in the Gateway.

## [0.2.0] - 2025-01-15 (MACAW Refactor)

### Added
- **MACAW Architecture:** Transitioned from Optimistic Parallelism to Sequential Blocking Architecture (Supervisor -> Planner -> Evaluator -> Executor -> Explainer).
- **Evaluator Agent:** New "System 3" control unit responsible for simulation and policy verification before execution.
- **Explainer Agent:** New monitoring unit for faithfulness checks.
- **Documentation:** Added `docs/MACAW_REFACTOR_GUIDE.md` and `ARCHITECTURE.md`.

### Changed
- **State Management:** Introduced `AgentState` with `evaluation_result` and `execution_result` fields.
- **Governance Flow:** Moved from "Check-then-Act" inside tools to "Plan-Verify-Execute" workflow at the graph level.

## [0.1.0] - 2024-12-01 (Initial Release)

### Added
- Initial release of the Financial Advisor with Hybrid Architecture (LangGraph + Google ADK).
- OPA Sidecar integration.
- NeMo Guardrails integration.
- Basic "Governed Trader" agent.
>>>>>>> origin/docs/agentic-gateway-analysis-15132879769016669359
