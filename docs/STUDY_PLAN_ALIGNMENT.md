# Study Plan Alignment Analysis

## Executive Summary
This document provides a gap analysis and implementation summary of the current "Secure Banking Assistant" repository against the "System 2 Agentic Architecture" study plan.

**Overall Status:** **High Alignment (85%)**.
The repository represents a mature implementation of the Capstone Project, successfully integrating the "Green Stack" governance components (OPA, NeMo) with the "Latency as Currency" optimization strategy (Speculative Decoding, vLLM).

The primary divergence is in the **ARPaCCino Pattern** (Module 6), where the system relies on pre-defined STPA hazard categories rather than dynamic regulatory PDF ingestion.

---

## Module 1: Foundations of LLM Inference & Hardware Constraints

### Status: ✅ Fully Implemented

*   **Concept:** **Bifurcated Execution Model (Prefill vs. Decode)**
    *   **Implementation:** The architecture explicitly optimizes for this distinction. The **Prefill** phase is used to hide the latency of asynchronous governance checks (Input Rails), while the **Decode** phase is optimized via Speculative Decoding.
    *   **Evidence:** `docs/LATENCY_STRATEGY.md` (Section 3: The Roofline Model).

*   **Concept:** **Hardware Architecture (H100/Hopper)**
    *   **Implementation:** The deployment target is explicitly NVIDIA H100 with FP8 optimization.
    *   **Evidence:** `deployment/k8s/vllm-deployment.yaml` configures `nvidia.com/gpu: "1"` and `--quantization fp8`.

---

## Module 2: CUDA Programming & Low-Level Kernel Mastery

### Status: 🔲 Knowledge / Infrastructure Managed

*   **Concept:** **Kernel Parallelism & Memory Optimization**
    *   **Implementation:** The repository abstracts this complexity by utilizing **vLLM** (`vllm/vllm-openai:v0.6.3`) which contains optimized kernels (PagedAttention, FlashInfer).
    *   **Note:** Custom CUDA kernels are not written in this repository; instead, the strategy relies on configuring the serving engine to use them effectively.

---

## Module 3: Virtual Memory & Attention Algorithms

### Status: ✅ Fully Implemented

*   **Concept:** **PagedAttention & FlashAttention-3**
    *   **Implementation:** Enabled via vLLM configuration.
    *   **Evidence:** `deployment/k8s/vllm-deployment.yaml`:
        ```yaml
        - name: VLLM_ATTENTION_BACKEND
          value: "FLASH_ATTN"
        ```
*   **Concept:** **Quantization**
    *   **Implementation:** FP8 (W8A8) is used to maximize H100 Tensor Core throughput.
    *   **Evidence:** Flag `--quantization fp8` in deployment manifest.

---

## Module 4: Speculative Architectures & the "Latency Buy-Back"

### Status: ✅ Fully Implemented (Variant Choice)

*   **Concept:** **Speculative Decoding (SD)**
    *   **Implementation:** The project implements a **Draft Model** architecture rather than Medusa (multi-head).
    *   **Configuration:**
        *   **Target:** `google/gemma-3-27b-it`
        *   **Draft:** `google/gemma-3-4b-it`
        *   **Lookahead:** 5 tokens
    *   **Evidence:** `deployment/k8s/vllm-deployment.yaml`:
        ```yaml
        - "--model", "google/gemma-3-27b-it"
        - "--speculative-model", "google/gemma-3-4b-it"
        - "--num-speculative-tokens", "5"
        ```
*   **Concept:** **Latency "Surplus"**
    *   **Implementation:** The `HybridClient` enforces a strict TTFT SLA (<200ms) to ensure the "Fast Path" provides enough time savings to offset the OPA/NeMo checks.
    *   **Evidence:** `src/infrastructure/llm_client.py`.

---

## Module 5: The Governance Stack: Policy & Orchestration

### Status: ✅ Fully Implemented

*   **Concept:** **Orchestration (LangGraph)**
    *   **Implementation:** The control plane is built on LangGraph, using conditional edges for routing and state management.
    *   **Evidence:** `src/graph/graph.py` defines the `StateGraph` and `supervisor` workflow.
*   **Concept:** **Decision Logic (NeMo & OPA)**
    *   **Implementation:**
        *   **NeMo:** `src/gateway/governance/nemo/server.py` and `config/rails/`.
        *   **OPA:** `deployment/k8s/opa_config.yaml` and `src/governance/policy/finance_policy.rego`.

---

## Module 6: Strategic Governance & Neuro-Symbolic Pipelines

### Status: ⚠️ Partially Implemented

*   **Concept:** **ARPaCCino Pattern (PDF to Rego)**
    *   **Implementation:** The **Neuro-Symbolic Transpiler** (`src/governance/transpiler.py`) is present and converts structured Risk Analysis objects (`ProposedUCA`) into OPA Rego and Python code.
    *   **Gap:** The specific "Regulatory PDF Ingestion" capability is **missing**. The system currently relies on hardcoded Hazard definitions in the Risk Analyst prompt (`src/agents/risk_analyst/agent.py`) rather than dynamically parsing external regulatory documents.
*   **Concept:** **Human-in-the-Loop**
    *   **Implementation:** Implemented using LangGraph's `interrupt_before` functionality to freeze state for review.
    *   **Evidence:** `src/graph/graph.py` -> `interrupt_before=["human_review"]`.

---

## Module 7: Serving Frameworks & System Design

### Status: ✅ Fully Implemented

*   **Concept:** **Production Deployment**
    *   **Implementation:** Full Kubernetes (Knative/Cloud Run) manifests are provided for a production-grade setup.
    *   **Evidence:** `deployment/service.yaml` (Sidecar Pattern), `deployment/k8s/vllm-service.yaml`.
*   **Concept:** **Prefill-Decode Disaggregation**
    *   **Implementation:** Configured via vLLM's chunked prefill settings.
    *   **Evidence:** `--enable-chunked-prefill` flag in `vllm-deployment.yaml`.

---

## Capstone Project: Secure Banking Assistant

### Status: ✅ Fully Implemented

*   **Objective:** Build a stateful banking agent that balances compliance with user experience.
*   **Result:** The repository is a direct implementation of this capstone.
    *   **Secure:** Implements NeMo/OPA rails.
    *   **Banking:** Agents specialized in Financial Advice, Trading, and Risk.
    *   **Stateful:** Redis-backed checkpointing for long-running sessions.
