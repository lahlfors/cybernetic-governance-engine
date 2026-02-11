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

### Strategy (The "Secret Manager Pattern")
We follow the official [Google Cloud Secret Manager Pattern](https://cloud.google.com/security/products/secret-manager).

1.  **Kubernetes Secrets (Primary Performance Path):**
    *   Secrets are injected as Environment Variables via `envFrom` in Deployment manifests.
    *   This is standard for high-performance apps.

2.  **Google Secret Manager (Resilient Fallback):**
    *   If an environment variable is missing AND `ENV=production`, the application attempts to fetch the secret directly from GSM.
    *   **Authentication:** Uses Workload Identity (Service Account) implicit auth.
    *   **Naming Convention:** Auto-maps environment keys to secret IDs: `BROKER_API_KEY` -> `broker-api-key`.
    *   **Path:** `projects/{PROJECT_ID}/secrets/{secret-id}/versions/latest`.

3.  **Local Development:**
    *   `.env` files are supported locally but ignored if `ENV=production`.

## 4. Compute Decisions
*   **vLLM:** Split into `vllm-fast` (CPU/Light GPU) and `vllm-reasoning` (A100/H100) to optimize cost vs. latency.
*   **Gateway:** Stateless gRPC service, horizontally scalable.
