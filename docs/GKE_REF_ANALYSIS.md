# Research Report: Refactoring Gateway & NeMo to GKE

## 1. Executive Summary

This report analyzes the feasibility and steps required to consolidate the Governed Financial Advisor deployment onto **Google Kubernetes Engine (GKE)**, removing all dependencies on **Google Cloud Run**.

**Findings:**
*   The current deployment script (`deployment/deploy_all.py`) **already targets GKE** by applying Kubernetes manifests.
*   The documentation (`deployment/README.md`) incorrectly states the system is deployed to Cloud Run, reflecting a legacy or alternative architecture.
*   The Gateway and NeMo services are stateless and fully compatible with GKE.
*   Refactoring is primarily a **cleanup task**: removing misleading documentation, legacy Terraform code, and "Cloud Run-isms" (like specific logging formats or port conventions) from the source.

**Recommendation:** **Proceed with GKE consolidation.** It provides better support for the system's hybrid inference requirements (GPU nodes for vLLM) and internal networking (gRPC) than Cloud Run. *(Update: This migration is now complete, including the Langfuse observability stack moving to GKE with an OpenTelemetry collector).*

---

## 2. Current State Analysis

### 2.1. Deployment Artifacts
*   **`deployment/deploy_all.py`**: This script builds containers and runs `kubectl apply`. It does **not** contain `gcloud run deploy` commands. It is already a GKE deployment script.
*   **`deployment/terraform/`**:
    *   `gke.tf`: Provisions a GKE Standard cluster with GPU pools (L4/T4).
    *   `deploy.tf`: References a missing script `deployment/deploy_sw.py` via a `local-exec` provisioner. This is likely dead code or a broken link to a legacy Cloud Run deployment method.
*   **`deployment/k8s/`**: Contains complete manifests for `gateway`, `nemo`, and `governed-financial-advisor` (backend).

### 2.2. Application Code
*   **Gateway (`src/gateway/server/main.py`)**: Contains a comment `# Configure JSON Logging for Cloud Run`. It uses `PORT` env var (Cloud Run convention), which is also standard in K8s containers.
*   **NeMo (`src/governance/nemo_server.py`)**: Standard FastAPI app. No specific Cloud Run dependencies.

### 2.3. Discrepancies
*   **Documentation vs. Code**: `deployment/README.md` explicitly describes a "Single Cloud Run Service" architecture with an OPA sidecar. The actual code (`deploy_all.py` + K8s manifests) deploys a distributed microservices architecture on GKE.

---

## 3. Pros & Cons: GKE vs. Cloud Run

| Feature | GKE (Recommended) | Cloud Run (Legacy/Alternative) |
| :--- | :--- | :--- |
| **GPU Support** | **Native**. Supports L4/T4/A100 with time-sharing and specific driver versions. Critical for vLLM. | **Limited**. GPU support is in Preview (sidecar/job) and restrictive. |
| **Networking** | **ClusterIP**. Fast, internal gRPC communication between Gateway and Agents. | **HTTP/gRPC**. Requires Service-to-Service auth (IAM) and goes through external load balancers (slower). |
| **State** | **Flexible**. Supports StatefulSets (Redis) if needed (though we removed Redis). | **Stateless**. No built-in state persistence without external services (Memorystore). |
| **Cost** | **Higher Baseline**. Control plane + Node pool cost. Efficient for high utilization. | **Scale-to-Zero**. Cheaper for infrequent usage, but cold starts affect agent latency. |
| **Governance** | **Sidecars**. OPA/NeMo as true sidecars or separate services in the same mesh. | **Multi-Container**. Supported, but harder to debug and limits resource isolation. |

---

## 4. Refactoring Strategy

To "remove all usage of Cloud Run" and finalize the GKE shift, the following steps are required:

### Phase 1: Cleanup Terraform & Scripts
1.  **Delete `deployment/terraform/deploy.tf`**: It references a missing script and tries to trigger a deployment logic that doesn't match `deploy_all.py`.
2.  **Verify `deploy_all.py`**: Ensure it doesn't have any hidden flags for Cloud Run (none found in analysis).

### Phase 2: Code Cleanup
1.  **Update Gateway Logging**: Remove explicit "Cloud Run" logging comments/formatters if they are too specific (though JSON logging is good for GKE too).
2.  **Standardize Ports**: Ensure K8s manifests and `Dockerfile`s agree on ports (50051 for Gateway, 8000 for NeMo) without relying on injected `$PORT` unless preferred.

### Phase 3: Documentation Overhaul
1.  **Rewrite `deployment/README.md`**: Remove "Cloud Run" architecture. Describe the GKE Microservices architecture (Agent -> Gateway -> vLLM/NeMo).
2.  **Update `ARCHITECTURE.md`**: Ensure the deployment section matches the GKE reality.

---

## 5. Final Recommendation

**Execute the GKE Consolidation Plan.**

The system has arguably already migrated to GKE in code, but the documentation and some Terraform vestiges are stuck in a "Cloud Run" past. Cleaning this up will reduce confusion and align the codebase with the actual infrastructure (GKE + GPU Nodes) required for the Agentic Gateway and vLLM components.
