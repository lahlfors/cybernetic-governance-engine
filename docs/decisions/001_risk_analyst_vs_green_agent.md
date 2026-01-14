# ADR 001: Retention of Risk Analyst alongside Green Agent

## Status
Accepted

## Context
With the introduction of the **Green Agent** (System 2 Verified Evaluator), which enforces deterministic safety rules (OPA, STPA, Logic), a question arises: **Should we replace the existing "Risk Analyst" agent with the Green Agent?**

The system currently has two "risk" nodes:
1.  **Risk Analyst (System 1):** An LLM-based agent that evaluates market conditions, strategy viability, and qualitative risks.
2.  **Green Agent (System 2):** A rule-based agent that audits plans for policy violations, unsafe control actions, and logical inconsistencies.

## Analysis

### Option A: Replace Risk Analyst (Green Agent Only)
In this scenario, the Planner sends strategies directly to the Green Agent.

**Pros:**
*   **Simplicity:** Reduces graph complexity (one fewer node).
*   **Latency:** Removes one LLM call from the critical path.
*   **Determinism:** "Risk" becomes purely binary (Pass/Fail) based on codified rules.

**Cons:**
*   **Loss of Nuance:** The Green Agent cannot detect "Soft Risks" (e.g., "This strategy is compliant but unwise given the current macro environment").
*   **Context Blindness:** Rules are rigid. They cannot reason about "Implied Volatility" unless explicitly coded.
*   **No "Advice":** The Green Agent says "NO" (with a rule ID). The Risk Analyst says "NO, because liquidity is drying up in Asian markets, suggesting you switch to...". The planner needs this rich feedback to improve.

### Option B: Hybrid Model (Retain Both)
The current architecture: Planner -> Risk Analyst -> Green Agent -> Trader.

**Pros:**
*   **Defense in Depth:**
    *   *Risk Analyst* filters out "Bad Ideas" (Unprofitable, Unwise).
    *   *Green Agent* filters out "Dangerous Actions" (Illegal, Catastrophic).
*   **Specialization:**
    *   Risk Analyst focuses on **Market Risk** (Will I lose money?).
    *   Green Agent focuses on **System/Compliance Risk** (Will I break the law/system?).
*   **Feedback Quality:** The Risk Analyst provides semantic reasoning to the planner, while the Green Agent provides hard constraints.

## Decision
**We will RETAIN the Risk Analyst.**

The two agents serve fundamentally different purposes in the **System 1 / System 2** cognitive architecture:
*   **Risk Analyst is the "Critic" (System 1):** It uses intuition and broad knowledge to evaluate *quality*.
*   **Green Agent is the "Gatekeeper" (System 2):** It uses strict rules to evaluate *safety*.

## Final Recommendation
Do not merge these roles. A strategy can be "Safe" (passed Green Agent) but "Stupid" (failed Risk Analyst). We need to catch both.
