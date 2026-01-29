# TPU Migration: Refactor Recommendation

## Executive Summary
We have successfully refactored the deployment architecture to prioritize **Google TPU v5e** ("Native Compute") for the vLLM inference layer, replacing NVIDIA L4 as the default.

## Changes Implemented

### 1. Deployment Configuration (`deployment/deploy_all.py`)
*   **Default Profile:** The `production` configuration matrix now targets `tpu-v5-lite-podslice` (TPU v5e).
*   **Topology:** Configured for **1 Host / 8 Chips** (`2x4` topology) with Tensor Parallelism (`TP=8`). This utilizes the full v5e host for maximum memory bandwidth.
*   **Legacy Fallback:** The previous NVIDIA L4 configuration is preserved under `legacy_gpu`, accessible via `--accelerator gpu`.

### 2. Manifest Generation
*   **Dynamic Resources:** The script now injects `google.com/tpu` resource limits instead of `nvidia.com/gpu` when TPU is selected.
*   **Node Selectors:** automatically applies `cloud.google.com/gke-tpu-accelerator` and `cloud.google.com/gke-tpu-topology` selectors.

## Trade-off Analysis

| Feature | TPU v5e (New Default) | NVIDIA L4 (Legacy) |
| :--- | :--- | :--- |
| **Cost** | **Lower** (~$0.70/hr spot for 8 chips) | Medium (~$0.56/hr per L4) |
| **Throughput** | **High** (High Bandwidth Memory) | Medium |
| **Latency (TTFT)** | Moderate (No Speculative Decoding yet) | **Low** (Supports Speculative Decoding) |
| **Native Integration** | **Native** (Google Silicon) | Third-Party |
| **Structured Gen** | Supported (Pallas/XLA) | Supported (CUDA) |

## Recommendation
**Adopt TPU v5e.**
While Speculative Decoding is currently experimental on TPUs (impacting ultra-low latency), the cost/performance ratio and "Native" alignment make it the correct strategic choice for this architecture. The high memory bandwidth of 8x v5e chips (aggregated) provides excellent throughput for batch processing and heavy reasoning tasks.

**Verification:**
Run `python3 deployment/deploy_all.py --project-id ...` to deploy the TPU stack.
Run `python3 deployment/deploy_all.py ... --accelerator gpu` to fallback to NVIDIA.
