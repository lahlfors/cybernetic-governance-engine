# vLLM Feasibility Analysis & Recommendation

## Executive Summary
This document originally analyzed the feasibility of migrating from **Google Vertex AI (ADK)** to **vLLM**.

**Status:** **Decision Made (Go).**
We are moving to a **Hybrid Inference** architecture.
- **Production:** Deploy vLLM on GKE/Cloud Run with NVIDIA H100 GPUs for the "Fast Path".
- **Fallback:** Retain Vertex AI for reliability and complex reasoning tasks.

## 1. Original Environment Assessment (Sandbox)
*   **Command:** `nvidia-smi`
*   **Result:** `Command not found` (CPU Only)
*   **Implication:** Local vLLM execution in the sandbox is mocked or requires external endpoints.

## 2. Trade-Off Analysis: Vertex AI vs. vLLM

| Feature | Google Vertex AI (Reliable Path) | vLLM (Fast Path) |
| :--- | :--- | :--- |
| **Latency (TTFT)** | Moderate (~500ms - 1s). Network overhead. | **Ultra-Low** (<20ms). Local memory access via PagedAttention. |
| **Throughput** | Scalable but limited by quota. | **High**. Continuous batching. |
| **Speculative Decoding** | Supported via endpoints. | **Native & Optimized** (Gemma 3 27B/4B). |
| **Management** | Serverless / Managed Service. | Self-Hosted (K8s/Docker). High operational complexity. |

## 3. The "Governance Budget" Implications
The "Governance Budget" (Section 1.3) requires strict safety checks that consume latency. We fund this budget by "buying back" time using Speculative Decoding on the vLLM stack.

## 4. Final Architecture (Phase 2)

### Deployment Strategy
1.  **Kubernetes (GKE):** Deploy vLLM as an internal service.
    *   **Hardware:** NVIDIA H100 (1x GPU).
    *   **Model:** `google/gemma-3-27b-it` (Target) + `google/gemma-3-4b-it` (Draft).
    *   **Optimization:** FP8 Quantization + FlashAttention-3.
2.  **Hybrid Client:**
    *   Routes requests to vLLM first.
    *   Falls back to Vertex AI if TTFT > 200ms.

See [docs/LATENCY_STRATEGY.md](docs/LATENCY_STRATEGY.md) for the detailed strategy.
