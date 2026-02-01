# Deployment Strategy: Vertex AI Agent Engine Hybrid

## Executive Summary

This document defines the deployment strategy for the **Governed Financial Advisor** using **Vertex AI Agent Engine**.

**Strategic Shift:**
We are moving from a "Self-Hosted Agent" model (Agent on Kubernetes/Cloud Run) to a **Managed Agent** model (Agent on Vertex AI Agent Engine). This leverages Google's managed runtime for the reasoning layer while retaining the high-performance GKE infrastructure for the inference layer.

## 1. Architecture Overview

The system adopts a **Hybrid Cloud Architecture** distributed across Managed Services and Kubernetes.

```mermaid
graph TD
    User([User Browser]) -->|HTTPS| UI[UI Service<br/>(Cloud Run)]
    UI -->|Rest API| AE[Agent<br/>(Vertex AI Agent Engine)]

    subgraph "Reasoning Plane (Managed)"
        AE
    end

    AE -->|gRPC/PSC| GW[Gateway Service<br/>(Cloud Run)]

    subgraph "Governance Plane (Serverless)"
        GW
        OPA[OPA Engine<br/>(In-Process)]
    end

    GW -->|VPC Egress| GKE{GKE Cluster<br/>(Private)}

    subgraph "Inference Plane (Kubernetes)"
        GKE -->|Internal HTTP| vLLM[vLLM Service<br/>(NVIDIA L4 GPUs)]
        GKE -->|Internal TCP| Redis[Redis<br/>(State Store)]
    end
```

---

## 2. Component Placement Analysis

### 2.1. The Agent (Reasoning Engine)
*   **Selected Platform:** **Vertex AI Agent Engine**
*   **Role:** "The Strategist" (System 2). Runs the LangGraph control flow.
*   **Rationale:**
    *   **Managed Runtime:** Offloads the complexity of packaging and scaling the Python agent runtime.
    *   **Observability:** Native integration with **Cloud Trace** and **Vertex AI Evaluation**.
    *   **Integration:** Seamless "Function Calling" and tool integration with Google ecosystem.
*   **Deployment:** Via `gcloud ai reasoning-engines create` or Terraform `google_vertex_ai_reasoning_engine`.

### 2.2. The Gateway (The Governor)
*   **Selected Platform:** **Cloud Run (Microservice)**
*   **Role:** "The Front Door". Enforces Policy (OPA), Safety, and Routing.
*   **Rationale:**
    *   **Accessibility:** The Agent (running in Google's tenant) needs a reachable endpoint. Cloud Run provides a secure, IAM-protected HTTPS/gRPC URL (`https://gateway-xyz.run.app`) automatically.
    *   **Identity Boundary:** Acts as the **Security Boundary**. The Agent Identity (Service Account A) invokes the Gateway. The Gateway Identity (Service Account B) is the *only* identity permitted to access the VPC and vLLM.
    *   **Scale:** Scales to zero when no reasoning is happening.
*   **Connectivity:**
    *   **Ingress:** Accessible via public internet (IAM Protected) or Private Service Connect (PSC).
    *   **Egress:** Uses **Direct VPC Egress** to access the GKE Internal Network.

### 2.3. Inference Engine (vLLM)
*   **Selected Platform:** **GKE (Standard)**
*   **Role:** "The Muscle" (System 1). Host the Llama-3.1-8B model on NVIDIA L4 GPUs.
*   **Rationale:**
    *   **Hardware:** Requires persistent access to GPUs. Cloud Run GPU (preview) is not yet suitable for high-throughput vLLM serving with large KV caches.
    *   **State:** vLLM benefits from a stable, long-running process to maintain the KV cache hot.
    *   **Cost:** Committed Use Discounts on GKE nodes are more cost-effective for 24/7 inference than on-demand serverless GPUs.

### 2.4. User Interface
*   **Selected Platform:** **Cloud Run**
*   **Rationale:** Standard, low-cost hosting for the Streamlit/React frontend.

---

## 3. Network & Security Architecture

### 3.1. Agent -> Gateway (The Bridge)
This is the critical link. The Agent runs in a Google-managed environment (Tenant Project), while the Gateway runs in your Project.

*   **Mechanism:** **Public Endpoint with IAM Auth**.
*   **Protocol:** gRPC (HTTP/2).
*   **Security:**
    1.  Gateway Cloud Run Service is deployed with `--no-allow-unauthenticated`.
    2.  Agent Service Account is granted `roles/run.invoker` on the Gateway Service.
    3.  Agent attaches OIDC Token to every gRPC request.

*Alternative (PSC):* If strict "No Public IP" compliance is required, we can use Private Service Connect. However, for this phase, IAM-protected Public Endpoint is recommended for simplicity and is secure (Google Infrastructure validates the token before traffic reaches the container).

### 3.2. Gateway -> vLLM (The Tunnel)
The Gateway needs to reach `http://vllm-inference.governance-stack.svc.cluster.local`.

*   **Mechanism:** **Direct VPC Egress**.
*   **Configuration:**
    *   Cloud Run Service configured with `--vpc-connector` or `--vpc-egress=all-traffic`.
    *   VPC Firewall Rules allowing the Cloud Run Subnet to talk to the GKE Pod CIDR.

---

## 4. Pros & Cons of this Strategy

| Feature | Pros | Cons |
| :--- | :--- | :--- |
| **Management** | **High.** Agent OS and runtime are fully managed. No Dockerfiles for the Agent logic. | **Low Control.** Limited control over the Agent's underlying python environment compared to a raw container. |
| **Security** | **Excellent.** Strict separation of concerns. The "Brain" (Agent) is physically separated from the "Muscle" (GKE) and "Bank" (Gateway). | **Complexity.** Requires configuring IAM and Network paths between 3 distinct environments (SaaS, Serverless, K8s). |
| **Scalability** | **High.** Agent Engine and Cloud Run scale almost infinitely. GKE scales based on Node Pools. | **Cold Starts.** The Agent -> Gateway -> vLLM chain introduces multiple potential cold start points. |
| **Observability** | **Unified.** Agent Engine pushes traces to Cloud Trace. Gateway pushes traces to Cloud Trace. We get a full distributed trace. | **Fragmented Logs.** Logs will be split between "Reasoning Engine" logs and "Cloud Run" logs. |

---

## 5. Migration Checklist

To implement this strategy, the following changes are required:

1.  **Refactor Agent:** Ensure `src/governed_financial_advisor` is compatible with the `reasoning_engines` SDK contract.
2.  **Update Deployment Script (`deploy_sw.py`):**
    *   Add logic to `tar` the agent code.
    *   Add logic to call `reasoning_engines.ReasoningEngine.create()`.
3.  **Terraform Updates:**
    *   Enable `aiplatform.googleapis.com`.
    *   Ensure Cloud Run has VPC Access to GKE.
4.  **Gateway Refactor:** Ensure the Gateway is deployed as a standalone Cloud Run service (as per `docs/AGENTIC_GATEWAY_ANALYSIS.md`).

## 6. Final Recommendation

**Approve the Hybrid Architecture.**

*   **Agent:** Vertex AI Agent Engine.
*   **Gateway:** Cloud Run (Separate Service).
*   **Inference:** GKE.

This aligns with the user's "Hard Requirement" and provides the most "Cloud Native" governance model.
