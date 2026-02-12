# GKE Inference Gateway Analysis for Sovereign Architecture

## Executive Summary

This document analyzes the feasibility and impact of migrating the current "Sovereign" AI architecture (Split-Brain: Reasoning vs. Governance) to use Google Kubernetes Engine (GKE) Inference Gateway.

Currently, the `GatewayService` manually routes requests to distinct vLLM services (`vllm-reasoning` and `vllm-governance`) via the `GatewayClient` application logic. Adopting GKE Inference Gateway would move this routing to the infrastructure layer, enabling advanced traffic management, autoscaling, and priority handling critical for regulatory compliance (SR 11-7).

**Recommendation:** **ADOPT** for Production environments to ensure high availability for governance checks, while maintaining the current application-level routing for Local Development.

---

## 1. Current Architecture vs. Proposed Architecture

### Current State (Application-Side Routing)
*   **Logic:** `src/gateway/core/llm.py` (`GatewayClient`) contains if/else logic to select the backend based on `mode` (e.g., `planner` -> `vllm-reasoning`, `fast` -> `vllm-governance`).
*   **Infrastructure:** Two separate Kubernetes Services (`vllm-reasoning`, `vllm-governance`).
*   **Scaling:** Standard HPA based on CPU/Memory (reactive).

### Proposed State (GKE Inference Gateway)
*   **Logic:** `GatewayClient` points to a single endpoint (the Inference Gateway). It specifies a `model` name (e.g., `llama-3.1-8b-instruct`, `llama-3.2-3b-governance`).
*   **Infrastructure:**
    *   **Gateway:** A unified GKE Gateway resource.
    *   **InferencePools:** Custom resources defining the backend pools (`vllm-reasoning`, `vllm-governance`).
    *   **HTTPRoutes:** Rules mapping `model` names or headers to specific pools.
*   **Scaling:** Metric-based HPA (Queue Depth, KV Cache Usage) managed by the Gateway controller (proactive).

---

## 2. Cost/Benefit Analysis

### Pros (Benefits)

1.  **Criticality & Priority Handling (Governance)**
    *   **Feature:** The Inference Gateway supports **Priority** classes.
    *   **Impact:** We can assign higher priority to "Governance" traffic (System 2 checks). Even if the "Reasoning" (System 1) pool is saturated with complex queries, the Governance checks (which block trade execution) will be prioritized or routed to reserved capacity. This is vital for **SR 11-7 Model Risk Management**—safety checks must never fail due to congestion.

2.  **Optimized Autoscaling**
    *   **Feature:** Uses custom metrics like **Queue Length** and **KV Cache Usage** (Time-to-First-Token optimization).
    *   **Impact:** Scale up `vllm-reasoning` nodes *before* latency spikes, ensuring consistent performance for the Planner Agent. Standard CPU scaling is often too slow for LLM inference bursts.

3.  **Simplified Client Code**
    *   **Feature:** Single endpoint URL.
    *   **Impact:** `GatewayClient` becomes a standard OpenAI client. We remove the custom "Dual-Client" logic, reducing technical debt and making it easier to swap underlying models without code changes.

4.  **LoRA Adapter Support**
    *   **Feature:** Efficiently serves multiple fine-tuned adapters on a shared base model.
    *   **Impact:** Future-proofing. If we train specific LoRA adapters for "Risk Analysis" or "Compliance," we can serve them on the existing `vllm-reasoning` pool without deploying new heavy pods.

### Cons (Costs & Risks)

1.  **Environment Divergence (Local vs. Prod)**
    *   **Risk:** GKE Inference Gateway is a cloud-specific managed service. It does not exist in Docker Compose.
    *   **Mitigation:** We must maintain the `GatewayClient`'s ability to support "Direct Mode" (current logic) for local development, while switching to "Gateway Mode" (single URL) in production via `Config`.

2.  **Infrastructure Complexity**
    *   **Cost:** Requires installing Gateway API CRDs and managing new manifests (`InferencePool`, `InferenceGateway`).
    *   **Mitigation:** Use Kustomize overlays to keep production-specific resources separate from base deployment manifests.

3.  **Vendor Lock-in**
    *   **Risk:** Tightly coupled to GKE's implementation of the Gateway API for Inference.
    *   **Mitigation:** The underlying standard (Kubernetes Gateway API) is open. Switching clouds would require changing the *implementation* (e.g., to Istio or Traefik), but the *concept* remains similar.

---

## 3. Migration Strategy

To adopt this without disrupting the current workflow, we recommend a phased approach:

### Phase 1: Infrastructure Preparation (DevOps)
1.  Enable GKE Gateway API and Inference Extension on the cluster.
2.  Define `InferencePool` resources for `vllm-reasoning` and `vllm-governance`.
3.  Deploy the `InferenceGateway`.

### Phase 2: Application Update (Code)
1.  Update `src/gateway/core/llm.py`:
    *   Introduce `VLLM_GATEWAY_URL` env var.
    *   If `VLLM_GATEWAY_URL` is set: Use single client, routing by `model` name.
    *   If not set (Local/Legacy): Use existing dual-client logic.

### Phase 3: Traffic Cutover
1.  Deploy updated Gateway Service to Prod.
2.  Set `VLLM_GATEWAY_URL` to the internal IP of the Inference Gateway.
3.  Verify routing and priority handling.

---

## 4. Final Recommendation

**Proceed with GKE Inference Gateway adoption for the Production environment.**

The **Priority Handling** feature alone justifies the complexity, as it directly supports the "Neuro-Cybernetic" safety mandate: *Governance must always be available to block unsafe actions.* Using standard CPU scaling for the governance model is a safety risk during high load; the Inference Gateway mitigates this.

---

## 5. Deployment & Configuration Guide

To deploy the Inference Gateway and configure the application:

### Step 1: Apply Kubernetes Manifests

Apply the manifests located in `deployment/k8s/inference-gateway/`. This will create the `InferencePool`s, `Gateway`, and `HTTPRoute`s.

```bash
kubectl apply -f deployment/k8s/inference-gateway/
```

### Step 2: Retrieve the Gateway IP Address

Wait for the Gateway controller to assign an IP address to the `llm-gateway`.

```bash
# Check the status of the Gateway
kubectl get gateway llm-gateway -n default

# Extract the IP address directly
export GATEWAY_IP=$(kubectl get gateway llm-gateway -n default -o jsonpath='{.status.addresses[0].value}')
echo "Gateway IP: $GATEWAY_IP"
```

*Note: Depending on your cluster configuration, this might be an internal IP (ClusterIP) or an external LoadBalancer IP.*

### Step 3: Configure the Application

Update your deployment configuration (e.g., in `deployment/k8s/gateway-deployment.yaml` or via ConfigMap) to set the `VLLM_GATEWAY_URL` environment variable using the retrieved IP.

```yaml
env:
  - name: VLLM_GATEWAY_URL
    value: "http://<GATEWAY_IP>/v1"  # Replace <GATEWAY_IP> with the actual IP
```

Or, if using a `.env` file locally (simulating gateway mode):

```bash
VLLM_GATEWAY_URL=http://<GATEWAY_IP>/v1
```

Once this variable is set, the `GatewayService` will automatically switch to **Gateway Mode**, routing all LLM requests through this single endpoint.
