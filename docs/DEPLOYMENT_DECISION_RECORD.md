# Deployment Decision Record

## 1. Executive Summary
This document records key architectural decisions regarding the deployment of the Neuro-Cybernetic Governance system.

## 2. Infrastructure
*   **Platform:** Google Kubernetes Engine (GKE) Standard.
    *   **Reason:** Required for persistent GPU access (vLLM stateful sets) which is not supported by Cloud Run or Autopilot.
*   **Region:** `northamerica-northeast2` (Toronto) / `us-central1` (Backup).

## 3. Configuration & Secrets Management (Updated 2026-01-27)

### Decision: No `.env` Files in Production
*   **Problem:** Storing secrets in `.env` files is insecure and hard to rotate. It violates 12-factor app principles for secrets.
*   **Solution:** A tiered configuration strategy managed by `ConfigManager` (`src/governed_financial_advisor/infrastructure/config_manager.py`).

### Strategy
1.  **Kubernetes Secrets (Primary):**
    *   Secrets are injected as Environment Variables via `envFrom` in Deployment manifests.
    *   This is the standard, high-performance path.
    *   Managed via External Secrets Operator or CI/CD pipelines.

2.  **Google Secret Manager (Fallback):**
    *   If an environment variable is missing AND `ENV=production`, the application attempts to fetch the secret directly from GSM using Workload Identity.
    *   This ensures resilience: if K8s secrets are misconfigured, the app can still recover (fail-open for auth, fail-closed for logic).

3.  **Local Development:**
    *   `.env` files are still supported for local testing but are ignored in production builds.

## 4. Compute Decisions
*   **vLLM:** Split into `vllm-fast` (CPU/Light GPU) and `vllm-reasoning` (A100/H100) to optimize cost vs. latency.
*   **Gateway:** Stateless gRPC service, horizontally scalable.
