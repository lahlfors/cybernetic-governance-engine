# Migration Analysis: Moving Inference from NVIDIA GPUs to Google TPUs

## 1. Executive Summary

This report analyzes the feasibility, cost, and technical requirements of migrating the current **Gemma 3 27B** inference workload from **NVIDIA H100 GPUs** to **Google Cloud TPU v5e** on GKE.

**Key Takeaways:**
*   **Feasibility:** **High.** vLLM supports TPU v5e and Gemma 3 via the Pallas/XLA backend.
*   **Cost Savings:** **Significant (up to 80-90%).** TPU v5e offers a drastically lower price-per-hour compared to H100, especially with Spot pricing.
*   **Performance:** TPU v5e (8 chips) provides comparable memory bandwidth to a single H100 but requires **Tensor Parallelism (TP=8)** to match the throughput.
*   **Trade-offs:** We lose **Speculative Decoding** and **FP8 Quantization** support immediately, which may increase latency per token compared to the highly optimized H100 FP8 setup.

---

## 2. Cost Benefit Analysis

Comparison of the current Single H100 setup vs. equivalent TPU v5e topologies in `us-central1`.

| Hardware | Specs | Pricing (On-Demand) | Pricing (Spot) | Est. Monthly Cost (On-Demand) |
| :--- | :--- | :--- | :--- | :--- |
| **NVIDIA H100** (Current) | 80GB HBM3 | ~$10.00 - $13.00 / hr* | High Volatility | ~$7,300+ |
| **TPU v5e (4 chips)** | 64GB HBM2e | $4.80 / hr | ~$1.00 / hr | ~$3,500 |
| **TPU v5e (8 chips)** | 128GB HBM2e | $9.60 / hr | ~$2.00 / hr | ~$7,000 |

*\*Note: H100 pricing on Google Cloud (A3 instances) is often contract-based or scarce. Market rates used for comparison.*

### Recommendation on Topology
*   **Gemma 3 27B (BF16)** requires ~54GB of VRAM for weights alone.
*   **TPU v5e-4 (64GB Total):** Very tight. Leaves <10GB for KV Cache and activations. High risk of OOM under load.
*   **TPU v5e-8 (128GB Total):** **Recommended.** Ample room for large batch sizes and KV cache.
*   **Savings:** Even with 8 chips, TPU v5e is generally cheaper and more available than a single H100.

---

## 3. Feasibility & Feature Gaps

The migration involves switching the backing engine of vLLM from CUDA to XLA/Pallas.

| Feature | NVIDIA H100 Status | TPU v5e Status | Impact |
| :--- | :--- | :--- | :--- |
| **Model Support** | Gemma 3 Supported | Gemma 3 Supported | ✅ Low Risk |
| **Quantization** | FP8 (W8A8) | **BF16 Only** (FP8 Exp.) | ⚠️ Higher VRAM usage (2x), potentially lower throughput. |
| **Speculative Decoding**| Supported (Draft Model) | **Not Supported** | ❌ Higher latency per token. |
| **Attention Backend** | FlashInfer / FlashAttn | PagedAttention (XLA) | ✅ Functional parity. |

---

## 4. Critical Feasibility Assessment: The Latency Gap

The current architecture ("Latency as Currency") relies on a "Latency Surplus" to offset the 200–500ms overhead of governance checks (NeMo Guardrails & OPA).

### The Mathematical Problem
*   **Current State (H100 + SpecDec):**
    *   TTFT: ~15-30ms
    *   Surplus: ~170ms (available for Governance)
    *   Result: **SLA Met (<200ms)**
*   **Migrated State (TPU v5e + No SpecDec):**
    *   TTFT (Est.): ~50-80ms (due to lack of SpecDec + TP=8 overhead)
    *   Governance Overhead: ~200ms
    *   Total TTFT: ~250-300ms
    *   Result: **SLA Violation (>200ms)**

**Conclusion:** Migrating the "Fast Path" (User-Facing Inference) to TPU v5e at this stage presents a **High Risk** of consistent SLA violations. The loss of Speculative Decoding means we cannot generate tokens fast enough to "pay" for the governance overhead.

---

## 5. Technical Implementation Plan

### A. Infrastructure (GKE)
1.  **Create TPU Node Pool:**
    Create a new node pool in the GKE cluster using `ct5lp-hightpu-8t` machine type (TPU v5e, 8 chips).
    ```bash
    gcloud container node-pools create tpu-pool \
        --cluster=governance-cluster \
        --machine-type=ct5lp-hightpu-8t \
        --num-nodes=1 \
        --region=us-central1 \
        --node-locations=us-central1-a
    ```
2.  **Driver Config:**
    Ensure the cluster has TPU support enabled (no NVIDIA drivers needed on this pool).

### B. Deployment Manifest (`vllm-deployment.yaml`)
Changes required to the Kubernetes deployment:

1.  **Image:** Switch from `vllm/vllm-openai` to `vllm/vllm-tpu:latest`.
2.  **Resources:**
    ```yaml
    resources:
      limits:
        google.com/tpu: "8"  # Request full 8-chip slice
      requests:
        google.com/tpu: "8"
    ```
3.  **Environment Variables:**
    *   Remove `VLLM_ATTENTION_BACKEND`.
    *   Add `VLLM_TARGET_DEVICE="tpu"`.
4.  **Args:**
    *   Set `--tensor-parallel-size 8`.
    *   Remove `--quantization fp8`.
    *   Remove `--speculative-model ...`.

---

## 6. Revised Recommendation

Given the strict 200ms TTFT SLA required by the governance architecture:

1.  **Do NOT Migrate the "Fast Path" Yet:**
    Keep the user-facing inference on **NVIDIA H100 with Speculative Decoding**. The latency surplus is critical for your governance budget.

2.  **Migrate Offline Workloads:**
    Move batch jobs (e.g., Risk Analyst pipelines, Bulk Evidence generation) to **TPU v5e**. These workloads are throughput-sensitive but not latency-sensitive, making them perfect candidates for the 80% cost reduction of TPUs.

3.  **Monitor Speculative Decoding on TPU:**
    Wait for vLLM to stabilize Speculative Decoding on TPU (Pallas backend). Once this feature lands, re-evaluate the Fast Path migration.
