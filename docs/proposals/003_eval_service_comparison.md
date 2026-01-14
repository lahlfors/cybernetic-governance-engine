# Proposal 003: Vertex AI GenAI Evaluation Service for Rule Validation

## 1. Executive Summary
This proposal evaluates the **Vertex AI GenAI Evaluation Service** as a component of the Green Agent ecosystem. While the user inquired about using it for "identifying and defining new rule candidates," our analysis concludes that it is ill-suited for *discovery* (finding unknown unknowns) but excellent for *validation* (verifying known rules).

We recommend a **Hybrid Approach**:
1.  **Custom Pipeline (Proposal 002):** For *Unsupervised Discovery* of new risk clusters (using Clustering/Embeddings).
2.  **Vertex AI Eval Service:** For *Supervised Validation* of those rules once defined (using AutoSxS or Rapid Evaluation).

## 2. Capability Analysis

| Feature | Vertex AI Evaluation Service | Custom Rule Discovery Pipeline |
| :--- | :--- | :--- |
| **Primary Goal** | **Scoring & Comparison.** Measuring quality against *known* rubrics (Safety, coherence, groundedness). | **Discovery.** Finding *unknown* patterns and clusters in unstructured data. |
| **Methodology** | **Supervised/Reference-Based.** Requires a "Golden Dataset" or specific metric definition. | **Unsupervised.** Uses embedding clustering (HDBSCAN) to find dense regions of failure. |
| **Output** | Score (0-1), Win Rate, Explanation. | Clusters of keywords, Candidate Rule Definitions. |
| **Cost** | Per-evaluation pricing (AutoSxS is expensive). | Batch processing (Dataflow/Vertex Pipelines) is cheaper for bulk logs. |

## 3. Pros & Cons

### Vertex AI GenAI Evaluation Service
**Pros:**
*   **Managed Infrastructure:** No need to build custom evaluation harnesses.
*   **AutoSxS (Side-by-Side):** Excellent for regression testing ("Is Green Agent V2 safer than V1?").
*   **Standard Metrics:** Built-in safety checks (hate speech, harassment) come for free.

**Cons:**
*   **Not a Discovery Tool:** It cannot tell you "Concentration Risk is a problem" unless you *ask* it to measure Concentration Risk. It answers the question you ask, it doesn't propose new questions.
*   **Latency/Scale:** Designed for "Golden Datasets" (100-1k examples), not streaming log analysis (100k+ logs).

### Custom Pipeline (Proposal 002)
**Pros:**
*   **True Discovery:** Finds "unknown unknowns" by clustering semantic failures.
*   **Tailored:** Specific to STPA/Control Theory concepts (UCAs) rather than generic "Safety".

**Cons:**
*   **High Maintenance:** Requires maintaining the clustering logic and embedding models.

## 4. Final Recommendation: The "Discovery-Validation" Loop

We recommend integrating Vertex AI Evaluation Service specifically for **Step 5 (Verification)** of the Evolutionary Roadmap, while retaining the Custom Pipeline for **Step 3 (Analysis/Discovery)**.

### Revised Workflow
1.  **Generate Logs:** Simulation generates 10k interactions.
2.  **Custom Pipeline (Discovery):** Clusters logs, proposes "UCA-5: Regulatory Risk".
3.  **Human:** Approves UCA-5 and writes the code in `safety_rules.py`.
4.  **Vertex AI Eval (Validation):**
    *   Construct a "Golden Dataset" of 50 Regulatory Scenarios.
    *   Run **Rapid Evaluation** to score Green Agent's refusal rate on this dataset.
    *   *Gate:* If Refusal Rate < 95%, fail the release.

## 5. Next Steps
*   Adopt Proposal 002 for the "Nightly Discovery" job.
*   Adopt Vertex AI Evaluation for the "Release Gate" CI/CD step.
