# Green Agent Evolutionary Roadmap (2026-2027)

This document outlines the strategic evolution of the **Green Agent** (System 2 Verified Evaluator) from its current MVP state to a fully ISO 42001-compliant "Neuro-Cybernetic Controller."

## Current State (Phase 1: Initial Structure)
- **Logic:** Hybrid `OPAClient` (Policy) + `SafetyCheck` (STPA Rules).
- **Context:** Audits the *previous* message (the Plan) in the graph.
- **Feedback:** Structured feedback identifying specific UCA violations.
- **Rules:** Defined in `src/green_agent/safety_rules.py`.

---

## Phase 2: Neuro-Symbolic Logic (DomiKnowS)
**Goal:** Replace fragile keyword heuristics with logical constraint satisfaction.
**Timeline:** Months 4-6 (aligned with Fellowship Roadmap).

### Implementation Steps
1.  **Define Ontology:** Create a `TradingGraph` ontology defining entities (`Asset`, `Risk`, `Regulation`) and relations (`is_compliant_with`, `exceeds_threshold`).
2.  **Integrate AgenticDomiKnowS (ADS):**
    -   Deploy the **Instructor Agent** to decompose natural language plans into Knowledge Graphs.
    -   Deploy the **Generator Agent** to write DomiKnowS constraints (e.g., `ifL(HighRisk, impliesL(RequiresHedging))`).
3.  **Refactor Green Agent:**
    -   Replace `audit_plan` logic to call the ADS pipeline.
    -   *Gain:* Catch logical inconsistencies (e.g., "Buying volatile asset X without hedging Y") that keywords miss.

---

## Phase 3: Cognitive Continuity (Mamba/SSMs)
**Goal:** Detect "Slow-Moving" attacks and drift over long horizons.
**Timeline:** Months 7-9.

### Implementation Steps
1.  **Data Engineering:**
    -   Implement `LogExporter` to serialize full agent trace history (User + Planner + Risk + Green) into a linear token stream.
2.  **Model Integration:**
    -   Train/Fine-tune a **Mamba-2.8B** model on "Safe" vs. "Unsafe" trajectory logs.
    -   Deploy Mamba as a sidecar service (due to GPU requirements).
3.  **Refactor Green Agent:**
    -   Before auditing the *current* plan, query the Mamba service: `predict_safety(history_context)`.
    -   *Gain:* Detect strategies that are locally safe (single trade) but globally unsafe (over-leveraging over 100 turns).

---

## Phase 4: System Safety Control Structure (STPA)
**Goal:** Treat safety as a Control Problem, not a Reliability Problem.
**Timeline:** Months 10-12 (Capstone).

### Data Requirements (Rule Seeding)
To seed the STPA rules effectively, we need to extract "Unsafe Control Actions" (UCAs) from historical data.

#### Script: `scripts/analyze_risk_logs.py` (Implemented)
We have a script to:
1.  **Parse** the structured output of the `Risk Analyst`.
2.  **Cluster** the `risk_feedback` where `risk_status == "REJECTED_REVISE"`.
3.  **Map** clusters to STPA UCA categories.

### Defined Unsafe Control Actions (UCAs) - Currently Enforced
1.  **UCA-1: Unbounded Risk Commission** (Action executed without explicit risk controls).
2.  **UCA-2: Unsafe Context Execution** (Action taken in hazardous context, e.g., "All-In", "Short Volatility").
3.  **UCA-3: Authorization Bypass** (Action attempts to override previous denials).

---

## Next Steps
1.  **Gather Data:** Run simulations to populate risk logs using the new JSON output format.
2.  **Run Analysis:** Use `scripts/analyze_risk_logs.py` on real data to discover new UCAs.
3.  **Iterate:** Add new rules to `src/green_agent/safety_rules.py`.
