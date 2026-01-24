# vLLM Feasibility Analysis & Recommendation

## Executive Summary
This document analyzes the feasibility of migrating the inference infrastructure from **Google Vertex AI (ADK)** to **vLLM** (an open-source high-throughput inference engine).

**Recommendation:** **Retain Google Vertex AI** for the current sandbox environment but architect the solution to be "Inference Agnostic" for future production migration.

## 1. Environment Assessment
An investigation of the current runtime environment was conducted to determine suitability for running vLLM locally.

*   **Command:** `nvidia-smi`
*   **Result:** `Command not found`
*   **Implication:** The current sandbox environment does not have GPU acceleration enabled or available.

Since vLLM relies heavily on **PagedAttention** and CUDA kernels for its performance gains, running it on a CPU-only environment is either impossible (depending on version) or significantly slower than the managed Vertex AI API, defeating the purpose of the migration.

## 2. Trade-Off Analysis: Vertex AI vs. vLLM

| Feature | Google Vertex AI (Current) | vLLM (Proposed) |
| :--- | :--- | :--- |
| **Latency (TTFT)** | Moderate (~500ms - 1s). Network overhead to Google Cloud. | **Ultra-Low** (<20ms). Local memory access via PagedAttention. |
| **Throughput** | Scalable but limited by quota/concurrency limits. | **High**. Continuous batching maximizes GPU utilization. |
| **Speculative Decoding** | Supported (via specialized endpoints). | **Native & Optimized**. Essential for "Governance Funding". |
| **Management** | Serverless / Managed Service. No infra maintenance. | Self-Hosted (K8s/Docker). High operational complexity. |
| **Governance Compatibility**| Good. Supports function calling and structured output. | Excellent. Full control over logits and sampling loop. |
| **Cost** | Pay-per-token. | Fixed infrastructure cost (GPU instances). |

## 3. The "Governance Budget" Implications
The requirement emphasizes a "Governance Budget" (Section 1.3), suggesting that strict safety checks consume latency that must be "refunded" by faster inference.

*   **With Vertex AI:** We are limited by the API's latency. Optimistic Execution (parallel checks) is the *primary* optimization lever available.
*   **With vLLM:** We could utilize **Speculative Decoding** (using a draft model to verify safety constraints cheaply) to significantly speed up the "Happy Path".

## 4. Final Recommendation

### For this Capstone/Sandbox:
**Stay on Vertex AI.**
*   **Reason:** Lack of GPU hardware prevents local vLLM execution.
*   **Strategy:** Focus on **Architectural Latency Reduction** (Optimistic Execution, Parallel Branching) rather than **Inference Latency Reduction**.

### For Production:
**Migrate to vLLM on GKE (Google Kubernetes Engine) with GPU nodes.**
*   **Reason:** To achieve the sub-200ms latency target for high-frequency trading agents, network overhead must be eliminated.
*   **Architecture:** Deploy the "Safety Node" (OPA/NeMo) as a sidecar *in the same pod* as the vLLM container to use localhost networking or shared memory.
