# Agentic Gateway Analysis

**Consolidated Architecture: Gateway Service + NeMo Guardrails (Cloud Run)**

This document analyzes the architectural decision to consolidate the NeMo Guardrails service directly into the Gateway Service, deployed on Google Cloud Run. This approach simplifies operations and reduces latency for the Cybernetic Governance Engine.

## Motivation

Previously, the architecture used a standalone NeMo Service (gRPC/HTTP) communicating with the Gateway. This introduced:
1.  **Network Latency:** An extra hop for every safety check.
2.  **Operational Complexity:** Managing two separate services, deployments, and authentication flows.
3.  **Cold Start Issues:** Two separate containers needing warm-up.

By embedding NeMo logic directly into the Gateway process:
*   Safety checks become in-process function calls (<10ms).
*   Deployment is atomic (Code + Policy versioning).
*   Resource utilization is more efficient (shared memory).

## Architecture

### Components

1.  **Gateway Service (Cloud Run):**
    *   **Orchestrator:** FastAPI application handling tool requests and LLM proxying.
    *   **Governance Engine (Internal):**
        *   **NeMo Manager:** Initializes `LLMRails` on startup.
        *   **Presidio Analyzer:** Loaded once (singleton) with `en_core_web_sm` Spacy model.
        *   **OPA Client:** Async HTTP client for policy decisions.
    *   **LLM Client:** `HybridClient` using Google Gen AI SDK (Vertex AI) for reasoning.

2.  **Agent (Vertex AI Reasoning Engine):**
    *   Hosted on Google's managed LangChain runtime.
    *   Communicates with the Gateway via secure HTTP (Cloud Run invocation).

### PII Protection Flow

1.  **Input:** User text arrives at Gateway (`/chat` or tool call).
2.  **NeMo Check:** `NeMoManager.check_guardrails()` is called.
    *   **Input Rails:** Trigger `mask_sensitive_data` action.
    *   **Presidio:** Scans text for Email, Phone, SSN, Credit Card.
    *   **Masking:** Replaces PII with `<ENTITY_TYPE>`.
3.  **LLM Interaction:** The sanitized prompt is sent to Vertex AI (Gemini).
4.  **Output:** LLM response is checked again by NeMo Output Rails.
5.  **Result:** Safe, masked response returned to Agent/User.

## Deployment Strategy

*   **Platform:** Google Cloud Run (Fully Managed).
*   **Resources:**
    *   **Memory:** Increased to `2Gi` to accommodate Spacy models and NeMo overhead.
    *   **CPU:** 1 vCPU (scales to zero).
*   **Authentication:** Service-to-Service IAM (OIDC).
*   **Dependencies:** Docker image builds `nemoguardrails`, `presidio-analyzer`, `presidio-anonymizer`, `spacy`, and `langchain-google-vertexai`.

## Trade-offs

| Feature | Consolidated Gateway | Separate Service |
| :--- | :--- | :--- |
| **Latency** | **Low (In-Process)** | High (Network Hop) |
| **Complexity** | **Low (Single Artifact)** | High (Microservices) |
| **Scalability** | **High (Cloud Run Autoscaling)** | High (Independent Scaling) |
| **Coupling** | High (Policy tied to Code) | Low (Decoupled) |
| **Cold Start** | Slower (~5-10s load time) | Faster per-service |

**Conclusion:** For this specific governance use case, the latency and simplicity benefits of consolidation outweigh the coupling concerns. The atomic deployment ensures that code changes are always synchronized with the safety policies governing them.
