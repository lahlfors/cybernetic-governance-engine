# Cloud Run Deployment Analysis: Agentic Gateway

## Executive Summary

This document analyzes the strategy for deploying the gRPC **Agentic Gateway** (`src/gateway`) to Google Cloud Run. The primary decision is between deploying the Gateway as a **Sidecar Container** (same Cloud Run Service) or as a **Separate Microservice** (distinct Cloud Run Service).

**Recommendation:** Deploy as a **Separate Cloud Run Service (Microservice)**. This maximizes security isolation (Identity Separation) and allows independent scaling, despite a minor latency penalty.

---

## 1. Deployment Options

### Option A: Sidecar Container (Multi-Container Support)
Cloud Run supports deploying multiple containers in a single Service (Pod-like structure).
*   **Architecture:** `[Agent Container] <--(localhost:50051)--> [Gateway Container]`
*   **Latency:** Minimal (localhost loopback, <0.1ms).
*   **Security:** Shared Identity (Service Account). Both containers run as the same Google Service Account (GSA).
*   **Scaling:** Coupled. If the Agent scales to 10 instances, the Gateway scales to 10 instances.

### Option B: Separate Microservice (Service-to-Service)
Deploy the Gateway as its own Cloud Run Service.
*   **Architecture:** `[Agent Service] <--(gRPC/Network)--> [Gateway Service]`
*   **Latency:** Increased (Network Hop + Load Balancer + Auth Handshake). Est: 10-30ms.
*   **Security:** **Strong Isolation.** The Agent GSA can have *zero* permissions. The Gateway GSA holds the keys to the Exchange and Vertex AI. The Agent only has permission to `invoke` the Gateway.
*   **Scaling:** Decoupled. The Gateway can handle traffic from multiple Agent types or scale differently based on CPU load (e.g., Token Counting vs Reasoning).

---

## 2. Technical Feasibility (gRPC on Cloud Run)

Cloud Run fully supports gRPC (via HTTP/2).

*   **Requirement:** The Gateway Service must expose port `8080` (or configured port) and the client must use HTTP/2.
*   **Configuration:**
    ```yaml
    # serving.knative.dev/minScale: "1"  <-- Recommended to avoid Cold Starts
    containers:
      - image: gateway-image
        ports:
          - containerPort: 50051
            name: h2c  # Explicitly signal HTTP/2
    ```
*   **Authentication:** Cloud Run requires `Authorization: Bearer <OIDC_TOKEN>` for Service-to-Service calls. The Agent must fetch an ID Token for the Gateway audience.

---

## 3. Latency Impact Analysis

**The "Latency as Currency" Trade-off:**

| Metric | Sidecar (Option A) | Microservice (Option B) |
| :--- | :--- | :--- |
| **Connection Time** | ~0ms (Localhost) | ~20ms (DNS + TLS + Connect) |
| **Request RTT** | <0.1ms | ~5-10ms (internal Google network) |
| **Cold Start** | Shared (Single Wakeup) | Cascading (Agent wakes -> Calls Gateway -> Gateway wakes). |

**Evaluation:**
*   For **LLM Streaming**, the 20ms connection overhead is negligible compared to the 200ms+ TTFT of the LLM.
*   For **Tool Execution**, the 10ms overhead is acceptable given the Governance value.
*   **Cold Start Risk:** Cascading cold starts are the biggest risk for Option B. This can be mitigated by keeping `min_instances=1` for the Gateway.

---

## 4. Pros & Cons

### Option A: Sidecar
*   **Pros:** Ultra-low latency, simple networking (localhost), no auth overhead between containers.
*   **Cons:** **Security Violation.** The Agent container shares the Identity. If the Agent is compromised, it can steal the Gateway's credentials (e.g., using `gcloud auth print-access-token` from the metadata server). This defeats the purpose of the "Security Boundary".

### Option B: Microservice
*   **Pros:** **Zero Trust Architecture.** The Agent has *no credentials* except the ability to call the Gateway. The Gateway is the only entity with access to the Exchange API and sensitive Policy data. Independent Lifecycle (update Gateway without redeploying Agents).
*   **Cons:** Network Latency (~10ms), cascading cold starts, slightly more complex IaC (Terraform).

---

## 5. Final Recommendation

**Deploy as a Separate Microservice.**

The primary driver for this architecture is **Governance and Security** ("The Governor"). Option A (Sidecar) compromises security by sharing the Service Account identity. Therefore, Option B is the only viable choice for a high-integrity system.

**Implementation Plan:**
1.  **Containerize Gateway:** Create `Dockerfile.gateway`.
2.  **Infrastructure:** Define Cloud Run Service `gateway-service` with `http2` enabled.
3.  **Identity:** Create `sa-agent` (invoker) and `sa-gateway` (executor). Bind `roles/run.invoker` on `gateway-service` to `sa-agent`.
4.  **Client Update:** Update `GatewayClient` in the Agent to fetch OIDC tokens (`google.auth.default()`) and attach them to gRPC metadata.
