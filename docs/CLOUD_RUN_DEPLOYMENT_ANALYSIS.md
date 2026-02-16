# Cloud Run Deployment Analysis

**Architecture: Split Gateway & NeMo Services**

This document analyzes the alternative architectural pattern of deploying the Gateway Service and NeMo Guardrails as **separate** Cloud Run services, rather than consolidating them.

## Motivation

While consolidation offers latency benefits, splitting the services aligns with a microservices philosophy and may offer advantages in specific scaling or organizational scenarios.

## Architecture

### Components

1.  **Gateway Service (Cloud Run Service A):**
    *   **Role:** Orchestrator / Proxy.
    *   **Logic:** Lightweight FastAPI app.
    *   **Responsibility:** Handles tool routing, OPA checks, and calls the NeMo service for content verification.
    *   **Scaling:** Scales based on request throughput (IO bound).

2.  **NeMo Service (Cloud Run Service B):**
    *   **Role:** Governance Engine.
    *   **Logic:** NeMo Guardrails + Presidio + Spacy.
    *   **Responsibility:** Receives text, performs PII masking and safety checks, returns sanitized text.
    *   **Scaling:** Scales based on CPU/Memory usage (Compute bound).

### Communication

*   **Protocol:** HTTPS (gRPC or REST).
*   **Authentication:** Service-to-Service IAM (OIDC tokens).
*   **Latency:** Incurs network overhead (~20-50ms per check within the same region).

## Pros & Cons (vs. Consolidated)

| Feature | Split Architecture | Consolidated Architecture |
| :--- | :--- | :--- |
| **Scaling** | **Granular:** Scale NeMo (heavy) independently of Gateway (light). | **Unified:** Must scale the heavy container even for light tasks. |
| **Development** | **Decoupled:** Teams can iterate on Policy vs. Logic separately. | **Coupled:** Policy changes require redeploying the Gateway. |
| **Latency** | High: Network hop + serialization. | **Low:** In-process function call. |
| **Cost** | Potentially Higher: Min instances needed for *both* services to avoid cold starts. | Lower: Shared idle resources. |
| **Complexity** | High: IAM, networking, service discovery. | Low: Single deployment artifact. |
| **Cold Start** | **Critical Risk:** If NeMo scales to zero, Gateway waits 5-10s for it to wake up. | Managed: Gateway startup includes NeMo load. |

## Recommendation

**Status: Rejected for Initial MVP.**

**Reasoning:**
1.  **Latency is Currency:** In the "Cybernetic Governance" model, every millisecond counts for the safety check loop. Adding 50ms+ network overhead per interaction degrades the user experience.
2.  **Complexity:** Managing secure service-to-service authentication on Cloud Run adds significant Terraform/Deployment complexity for a relatively small codebase.
3.  **Cost:** Running two separate "min instance" sets to prevent cold starts doubles the idle cost.

**Future Consideration:**
If the NeMo logic becomes extremely heavy (e.g., loading 70B parameter local models), splitting it off to a GPU-enabled Cloud Run (or returning to GKE) would be necessary. For the current `en_core_web_sm` + API-based LLM design, consolidation is superior.
