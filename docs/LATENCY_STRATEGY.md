# Latency as a Tradeable Currency: High-Performance Inference Strategy

## 1. Executive Summary

To effectively navigate the pivot from a SaaS-based model to a self-hosted high-performance inference stack, this architecture treats **latency as a tradeable currency**. By leveraging the technical capabilities of NVIDIA H100 GPUs and Speculative Decoding with the **Gemma 3** model family, we create a latency "surplus" in the inference layer that "funds" the computational overhead of robust governance checks (NeMo Guardrails & OPA).

## 2. The Latency "Buy-Back" Math

The core justification for this infrastructure investment is the ability to offset the ~200–500ms overhead of governance rails by slashing Inter-Token Latency (ITL).

### 2.1 Speculative Decoding Acceptance Model (Gemma 3)

We utilize **Gemma 3-27B-Instruct** as the Target Model and **Gemma 3-4B-Instruct** as the Draft Model.

The expected number of accepted tokens per pass ($\tau$) is defined as:

$$
\tau = \frac{1 - \alpha^{\gamma+1}}{1 - \alpha}
$$

Where:
*   $\alpha$: The acceptance rate (probability that the 27B target agrees with the 4B draft).
*   $\gamma$: The number of speculative tokens proposed by the draft model (lookahead).

**Impact:** Since the 4B draft model is extremely lightweight, we can run larger lookahead windows. If $\alpha \ge 0.8$, effective generation speed increases by **2x–3x**. For a typical 50-token response, this reduces generation time significantly, creating a surplus that dwarfs the governance "tax".

### 2.2 Drafting Overhead Budget

For SD to be effective, the time cost of generating draft tokens must be less than the time saved by parallel verification. We define the **Drafting Overhead Budget** as:

$$
T_{draft} \cdot \gamma < T_{target} \cdot (\tau - 1)
$$

Since $T_{target}$ (27B) is significantly higher than $T_{draft}$ (4B), the budget allows for aggressive speculation.

## 3. The Roofline Model: Why This Works

Understanding the hardware bottlenecks is crucial for optimization.

### 3.1 Prefill Phase (Compute-Bound)
*   **Characteristics:** The GPU processes the entire prompt history in parallel.
*   **Bottleneck:** Raw TFLOPS (Tensor Cores).
*   **Governance Opportunity:** This phase is computationally intensive but has high latency. We execute **Input Rails (PII, Jailbreak)** asynchronously during this phase. Since the governance checks are I/O bound (network calls to OPA/NeMo), they overlap perfectly with the GPU's compute-bound work.

### 3.2 Decode Phase (Memory-Bound)
*   **Characteristics:** The GPU generates one token at a time. It must load the entire model weight matrix from VRAM for *every single token*.
*   **Bottleneck:** HBM3 Memory Bandwidth. The Compute Units (Tensor Cores) sit idle most of the time waiting for data.
*   **Optimization:** Speculative Decoding utilizes these idle Compute Units to verify multiple tokens in a single memory access, moving the workload back towards the compute-bound region of the Roofline.

## 4. Hardware Assumptions & Optimization

The deployment blueprint targets the **NVIDIA H100 (Hopper)** as the performance ceiling while maintaining compatibility with the A100.

### 4.1 NVIDIA H100 (Hopper) - The Target
*   **Feature:** **FlashAttention-3** with Tensor Memory Accelerator (TMA).
*   **Precision:** Native **FP8 (W8A8)** support.
*   **Benefit:** Doubles throughput and halves memory consumption compared to FP16.

### 4.2 Single-GPU Optimization (Gemma 3 27B)
Unlike Llama 70B which requires Tensor Parallelism across 4 GPUs, **Gemma 3-27B** fits comfortably on a **single H100 (80GB)** even with KVCache overhead.
*   **TP=1:** Eliminates inter-GPU communication overhead (NVLink latency).
*   **Efficiency:** Maximizes utilization of the single GPU's HBM3 bandwidth.
*   **Cost:** significantly reduces the hardware footprint required per replica.

## 5. Deployment Architecture: The Parallel Fast Path

### 5.1 Input Stage
NeMo/OPA input rails run asynchronously during the LLM's **Prefill** stage.
*   *Result:* Zero effective latency cost for input validation.

### 5.2 Output Stage (Async Stream-Validation)
1.  **Generation:** The LLM streams response chunks to the user immediately.
2.  **Verification:** The "Safety Node" validates these chunks in the background.
3.  **Intervention:** If a violation is detected (e.g., Toxic Output), the stream is interrupted, and a "Recall" message is sent.

### 5.3 Fallback Logic (Dual-Trigger)
To ensure reliability matching Vertex AI, the self-hosted client implements a dual-trigger fallback:
1.  **Hard Error:** Immediate fallback on 5xx errors or connection refusals.
2.  **SLA Violation:** If Time-To-First-Token (TTFT) > **200ms**, the request is cancelled and routed to Vertex AI.
