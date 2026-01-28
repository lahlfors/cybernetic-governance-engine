# Latency as Currency: Funding Governance with Inference Speed

This document outlines the performance strategy for the Cybernetic Governance Engine. The core philosophy is **"Latency as Currency"**: we must generate tokens fast enough to "pay for" the overhead of strict governance checks (NeMo, OPA, JSON Enforcement).

## The Governance Tax

Every safe generation incurs a latency penalty:
1.  **Semantic Guardrails (NeMo):** ~150-300ms (Input/Output checks).
2.  **Policy Evaluation (OPA):** ~20-60ms (Remote Service network hop + Rego eval).
3.  **Syntactic Enforcement (vLLM FSM):** ~50ms (with Prefix Caching).

To maintain a responsive user experience (Total Response Time < 2s for simple queries), the underlying inference engine must be exceptionally fast.

## The Solution: "The Enforcer" on NVIDIA L4

We utilize a dedicated, self-hosted inference node for structure enforcement, optimized for speed and cost.

### Hardware: NVIDIA L4 (24GB VRAM)
*   **Why:** The L4 is the most cost-effective GPU for models < 20B parameters.
*   **Capacity:** A single L4 can comfortably host `google/gemma-2-9b-it` (Require ~18GB VRAM in bfloat16) with room for KV cache.
*   **Throughput:** Capable of high token-per-second generation for JSON structures.

### Software: vLLM + Prefix Caching
We use **vLLM** with **Prefix Caching** enabled (`--enable-prefix-caching`).

#### How Prefix Caching Works
1.  **The Pattern:** Every governance request shares the same massive system prompt: "You are a governance engine. Output JSON matching this schema: { ... complex schema ... }".
2.  **The Cache:** vLLM hashes this prompt prefix and stores the KV (Key-Value) attention states in GPU memory.
3.  **The Hit:** When a new request comes in (different user data, same schema), vLLM skips computing attention for the schema definition.
4.  **The Result:** The "Time-To-First-Token" (TTFT) for the governance check drops from ~200ms to **<50ms**.

### Architecture Alignment

| Component | Model | Hosted On | Optimization |
|---|---|---|---|
| **Reasoning** | `gemini-2.5-pro` | Vertex AI (SaaS) | Deep semantic understanding. |
| **Governance** | `gemma-2-9b-it` | GKE (NVIDIA L4) | Prefix Caching + Guided JSON. |

## Latency Budget Example

**Scenario:** Risk Analyst generates a formal assessment.

1.  **Agent Reasoning (Gemini):** 1.5s (Thinking time)
2.  **Tool Call (Governance Client):**
    *   Network RTT: 10ms
    *   **vLLM TTFT (Cached):** 40ms
    *   Generation (100 tokens): 150ms
3.  **Total Governance Overhead:** ~200ms

**Result:** The user gets a structurally guaranteed, compliant response with minimal added delay compared to a raw LLM call.
