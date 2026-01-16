# Remediation Proposal: Real-Time Governance & Stateful Risk

**Status:** Proposed
**Date:** 2025-05-15
**Target:** Address gaps identified in `GAP_ANALYSIS_REPORT.md` (Feedback Loop Latency, Stateless Risk, Race Conditions).

## 1. Problem Statement
The current implementation suffers from three critical control failures:
1.  **High Latency:** Critical safety rules discovered by the Risk Analyst require a full service deployment to take effect (minutes vs milliseconds).
2.  **Ahistorical Analysis:** The Risk Analyst is stateless, preventing detection of "Salami Slicing" (temporal cumulative risks).
3.  **Race Conditions:** Policy updates are direct file overwrites without version control.

## 2. Solution 1: Dynamic Policy Injection (Bundle Server)

Move from "File-Based Policy" to "Bundle-Based Policy".

### Architecture
*   **Current:** OPA Sidecar loads `/policies/finance_policy.rego` from a mounted Secret.
*   **Proposed:** Configure OPA Sidecar to poll a signed Bundle URL (e.g., GCS bucket or Nginx endpoint).

### Implementation Steps
1.  **Update `deployment/opa_config.yaml`:**
    ```yaml
    services:
      - name: policy-bundle-server
        url: https://storage.googleapis.com/my-governance-bucket
    bundles:
      finance:
        service: policy-bundle-server
        resource: bundles/finance.tar.gz
        polling:
          min_delay_seconds: 10
          max_delay_seconds: 20
    ```
2.  **Update `offline_risk_update.py`:**
    *   Instead of writing `.rego` files locally, the script builds a tarball.
    *   Uploads the tarball to the GCS bucket.
    *   OPA Sidecars (polling every 10s) automatically hot-reload the new policy *without* container restart.

**Outcome:** Latency reduced from ~5 minutes (Deploy) to ~15 seconds (Poll).

## 3. Solution 2: Stateful Risk Memory (Redis)

Enable the Risk Analyst to see "Time".

### Architecture
Leverage the existing `src/infrastructure/redis_client.py` to store a "Risk Window".

### Implementation Steps
1.  **Create `src/green_agent/memory.py`:**
    ```python
    class RiskMemory:
        def add_transaction(self, user_id, amount, timestamp):
            # Store in Redis List (capped at 100 items)
            key = f"risk:history:{user_id}"
            redis_client.lpush(key, json.dumps({...}))
            redis_client.ltrim(key, 0, 99)

        def get_recent_volume(self, user_id, window_seconds=3600):
            # Sum amounts in the last hour
            ...
    ```
2.  **Update Risk Analyst Input:**
    *   Before calling the Risk Analyst agent, the `supervisor_node` retrieves `risk_memory.get_summary(user_id)`.
    *   Inject this summary into the agent's prompt: "Recent History: User traded $50k in last hour (5 small trades)."

**Outcome:** Agent can detect "Salami Slicing" (e.g., "5 trades of $9,999 in 10 minutes").

## 4. Solution 3: GitOps Workflow for Policy

Eliminate race conditions and enforce human review.

### Architecture
The `offline_risk_update.py` script acts as a bot, not a sysadmin.

### Implementation Steps
1.  **Integrate `PyGithub` or `gh` CLI:**
    *   Instead of `open(file, 'w')`, the script:
        1.  Checks out a new branch `risk/update-{timestamp}`.
        2.  Writes the transpiled Rego/Python code.
        3.  Commits and pushes.
        4.  Opens a Pull Request: "Risk Analyst: Discovered New Slippage Constraints".
2.  **CI/CD Pipeline:**
    *   Human or "Senior Agent" approves the PR.
    *   Merge triggers the "Bundle Builder" (Solution 1) to push the new artifact.

**Outcome:** Zero race conditions. Full audit trail of *who* changed the policy and *why*.

## 5. Summary of Impact

| Feature | Current State | Proposed State |
| :--- | :--- | :--- |
| **Policy Update** | File Overwrite (Unsafe) | GitOps PR (Audited) |
| **Activation Time** | Minutes (Redeploy) | Seconds (Hot Reload) |
| **Risk Context** | Single Plan (Stateless) | Temporal Window (Stateful) |
