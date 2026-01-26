# Changelog

All notable changes to this project will be documented in this file.

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
