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

**Critical Blocker:**
If your application relies on **Speculative Decoding** to meet strict TTFT (Time To First Token) or latency SLAs, the migration to TPU will degrade performance until that feature is stabilized in vLLM TPU.

---

## 4. Technical Implementation Plan

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

### C. Automation Scripts
Update `deployment/deploy_all.py` to support a new `--target tpu` flag that applies the above transformations dynamically.

---

## 5. Risks & Mitigation

1.  **Availability:** TPU v5e resources can be scarce in certain zones.
    *   *Mitigation:* Use GKE Autopilot or reserved capacity if guaranteed uptime is needed.
2.  **Latency Regression:** Loss of Speculative Decoding and FP8.
    *   *Mitigation:* Benchmark BF16 on TPU v5e-8. The high bandwidth of 8 chips often compensates for the lack of quantization.
3.  **Feature Lag:** vLLM TPU features lag behind CUDA.
    *   *Mitigation:* Monitor `vllm-project/tpu-inference` for updates on Speculative Decoding.

## 6. Conclusion

Moving to **TPU v5e (8-chip)** is a viable cost-reduction strategy that eliminates dependency on scarce H100 GPUs. However, it requires accepting a **"Plain BF16"** inference pipeline, sacrificing advanced optimizations like FP8 and Speculative Decoding.

**Recommendation:**
Proceed with a **Proof of Concept (PoC)** deployment on a standard GKE cluster to benchmark the actual latency of Gemma 3 27B on TPU v5e-8 before fully decommissioning the H100 setup.
