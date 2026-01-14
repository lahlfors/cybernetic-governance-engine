# ADR 002: Prevention of Hallucination in Green Agent Verification

## Status
Accepted

## Context
A critical vulnerability in Agentic AI is the "Recursive Hallucination Paradox": If we use an AI (System 2) to check an AI (System 1), what stops the checker from hallucinating that a dangerous plan is safe?

The user asked: *"What prevents the green agent from hallucinating decisions?"*

## Decision
The Green Agent (System 2 Verified Evaluator) is architected as a **Deterministic Code Execution Unit**, not a Probabilistic LLM Chain. It does not "think" or "decide" using a neural network; it **calculates** using formal logic.

## Technical Implementation (The 4 Layers of Determinism)

We have removed the LLM from the decision loop entirely for the verification step.

### Layer 1: Policy (OPA) -> Deterministic
*   **Mechanism:** Uses the Open Policy Agent (Rego).
*   **Guarantee:** Rego is a declarative language. Given Input X and Policy Y, the output is *mathematically proven* to be identical every time. It cannot "hallucinate" an exception.

### Layer 2: Safety (STPA) -> Deterministic
*   **Mechanism:** Python string matching (`if "short volatility" in plan_text`).
*   **Guarantee:** Substring matching is binary. It does not rely on semantic similarity or embedding vectors that might drift.

### Layer 3: Logic (Neuro-Symbolic) -> Hybrid
*   **Mechanism:** Predicate Logic on a Knowledge Graph.
    *   *Step 3a (Parsing):* Currently heuristic (Code). Future state uses a specialized extractor. This is the only point of potential error (missing an entity), but not *hallucination* (inventing an entity).
    *   *Step 3b (Reasoning):* `SymbolicReasoner` executes hard-coded Python rules (`if asset.vol > 8.0`). Math does not hallucinate.
*   **Guarantee:** If the inputs are parsed, the decision is rigorous logic.

### Layer 4: History (Cognitive Continuity) -> Deterministic
*   **Mechanism:** Statistical drift detection (Counting keyword frequency over time).
*   **Guarantee:** Arithmetic means are deterministic.

## Trade-Offs

| Feature | LLM-Based Verifier | Green Agent (Code-Based) |
| :--- | :--- | :--- |
| **Nuance** | High (Understands sarcasm, context) | Low (Literal interpretation) |
| **False Positives** | Low (Can be reasoned with) | High (Blocks "Safe" plans that use "Unsafe" words) |
| **Hallucination** | **High Risk** | **Zero Risk** |
| **Auditability** | Low (Opaque weights) | High (Line of code responsible) |

## Conclusion
We accept the cost of **rigidity** (False Positives) to gain the benefit of **certainty** (Zero Hallucination). The Green Agent acts as a "Circuit Breaker," not a "Philosopher."
