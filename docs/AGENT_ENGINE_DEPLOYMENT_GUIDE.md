# Deployment Guide: Vertex AI Agent Engine Hybrid

## Executive Summary

This document defines the implementation of the **Governed Financial Advisor** using **Vertex AI Agent Engine**.

**Strategic Shift:**
We have implemented a **Managed Agent** model (Agent on Vertex AI Agent Engine). This leverages Google's managed runtime for the reasoning layer while retaining the high-performance GKE infrastructure for the inference layer.

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

## 2. Component Placement

### 2.1. The Agent (Reasoning Engine)
*   **Platform:** **Vertex AI Agent Engine**
*   **Role:** "The Strategist" (System 2). Runs the LangGraph control flow.
*   **Deployment:** `deploy_sw.py --deploy-agent-engine` uses the Vertex AI SDK to pickle and upload the agent code (`src/governed_financial_advisor/reasoning_engine.py`).

### 2.2. The Gateway (The Governor)
*   **Platform:** **Cloud Run (Microservice)**
*   **Role:** "The Front Door". Enforces Policy (OPA), Safety, and Routing.
*   **Networking:**
    *   **Ingress:** Protected by IAM (`roles/run.invoker` granted to Agent SA).
    *   **Egress:** **Direct VPC Egress** is configured to route all traffic to the GKE network, allowing access to `vllm-inference` internal service.

### 2.3. Inference Engine (vLLM)
*   **Platform:** **GKE (Standard)**
*   **Role:** "The Muscle" (System 1). Host the Llama-3.1-8B model on NVIDIA L4 GPUs.
*   **Status:** Deployed via standard Kubernetes manifests (`deployment/k8s/`).

### 2.4. User Interface
*   **Platform:** **Cloud Run**
*   **Role:** Frontend. Connects to the Agent Engine.

---

## 3. Deployment Instructions

### 3.1. Prerequisite: Infrastructure (Terraform)
Run Terraform to create the Identity and Networking layer.

```bash
cd deployment/terraform
terraform apply -var="project_id=YOUR_PROJECT"
```
*Creates: `agent-engine-sa`, `gateway-sa`, Artifact Bucket, GKE Cluster.*

### 3.2. Deploy Application (Hybrid)
Run the Python orchestration script with the agent engine flag.

```bash
python3 deployment/deploy_sw.py \
  --project-id YOUR_PROJECT \
  --region us-central1 \
  --redis-host 10.x.x.x \
  --deploy-agent-engine
```

**What this does:**
1.  **Deploys GKE Infra:** Ensures vLLM is running.
2.  **Deploys Gateway:** Pushes the Gateway container to Cloud Run and links it to the vLLM internal endpoint.
3.  **Deploys Agent:** Pickles the local code, uploads it to GCS, and creates a `ReasoningEngine` resource in Vertex AI.

---

## 4. Implementation Details

### Identity & Security
*   **Agent Engine:** Runs as `agent-engine-sa`. Has `roles/run.invoker` on the Gateway.
*   **Gateway:** Runs as `gateway-sa`. Has `roles/aiplatform.user` (to call Gemini).
*   **Authentication:** The Agent uses `google.auth.default()` (in `GatewayClient`) to fetch an OIDC token when calling the Gateway.

### Code Adapters
*   `src/governed_financial_advisor/reasoning_engine.py`: Acts as the adapter class required by the Vertex AI SDK.
*   `src/governed_financial_advisor/infrastructure/gateway_client.py`: Refactored to support remote Cloud Run authentication.
