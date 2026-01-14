# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased] - 2026-01-14

### Added
- **Green Agent Capstone (System 2 Verification):**
    - Implemented `GreenAgent` class with 4-layer verification stack:
        1. **Policy (Layer 1):** OPA Integration.
        2. **Safety (Layer 2):** STPA-derived rules (UCA-1 to UCA-4).
        3. **Logic (Layer 3):** Neuro-Symbolic `SymbolicReasoner` for graph constraints.
        4. **History (Layer 4):** `HistoryAnalyst` for drift detection (Cognitive Continuity).
    - Integrated `GreenAgent` into LangGraph workflow (`src/graph/graph.py`).
    - Added comprehensive unit tests in `tests/test_green_agent.py`.
- **Automated Rule Discovery:**
    - Added data generation scripts: `scripts/simulate_risk_scenarios.py`.
    - Added analysis scripts: `scripts/analyze_risk_logs.py`.
    - Proposed Vertex AI Pipeline architecture in `docs/proposals/002_vertex_rule_discovery.md`.
    - Added reference pipeline implementation in `src/pipelines/rule_discovery.py`.
- **Verification Pipeline:**
    - Proposed Vertex AI GenAI Evaluation Service strategy in `docs/proposals/003_eval_service_comparison.md`.
    - Added reference verification script `src/pipelines/rule_verification.py`.
- **Documentation:**
    - Added `docs/GREEN_AGENT_EVOLUTION.md` detailing the 12-month roadmap.

### Changed
- **Risk Analyst Refactoring:**
    - Updated `RiskAnalyst` agent to output structured JSON (`RiskAssessment` schema).
    - Simplified agent prompt to rely on schema enforcement rather than verbose text instructions.
    - Updated `risk_analyst_node` adapter to parse JSON output.
- **Workflow Routing:**
    - Updated `router.py` to support `Risk -> Green -> Trader` flow.

### Removed
- Deleted legacy/broken `eval/` scripts to clean dead code.
