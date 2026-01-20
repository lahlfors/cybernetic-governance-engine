# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **Dynamic Control Barrier Function (CBF):** Implemented a hybrid safety architecture for the Drawdown Limit.
    - **Static Mechanism:** Hardcoded `check_drawdown_limit` in `nemo_actions.py` enforcing $h(x) = Limit - Value \ge 0$.
    - **Dynamic Policy:** Added `safety_params.json` support to allow the offline Risk Analyst to update safety thresholds without code deployment.
    - **Safety Hardening:** Implemented strict input sanitization, safe defaults (5%), and atomic file updates.
- **Red Teaming Tests:** Added `tests/test_red_teaming.py` to verify hot-reloading and resilience to corrupt configuration.
- **Transpiler Upgrade:** Updated `PolicyTranspiler` to extract safety parameters from identified UCAs.
