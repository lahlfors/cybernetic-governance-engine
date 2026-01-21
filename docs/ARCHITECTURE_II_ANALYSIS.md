# Architecture II Analysis: The Pragmatic Hybrid

## Overview

This document analyzes the shift from **Architecture I** (HTTP Sidecar) to **Architecture II** (In-Process Wasm + Cloud Run). This "Pragmatic Hybrid" approach balances the theoretical safety of neuro-symbolic reasoning with the practical performance requirements of production systems.

## Key Decisions

### 1. Latency: Adopt In-Process Wasm
**Decision:** Migrate governance logic from an HTTP Sidecar to an In-Process Wasm Library (`opa-wasm`).

*   **Problem with Arch I:** HTTP requests introduce network serialization and transport overhead (20-50ms per check). While acceptable for some, it limits the throughput of high-frequency agentic loops.
*   **Solution:** Loading the compiled Rego policy into memory allows governance to act as a direct function call (<1ms).
*   **Trade-off:** Requires a build step (`opa build -t wasm`) to compile policies, slightly increasing CI/CD complexity.

### 2. Execution Model: Synchronous Service (Reject Jobs)
**Decision:** Maintain the synchronous Web Service model (`Cloud Run Service`) and reject the "One Job per Request" proposal.

*   **Reasoning:** Spinning up a Kubernetes Job or Pod for every agent interaction introduces massive "cold start" latency (5-10s). For interactive financial advisors, this is unacceptable.
*   **Mitigation:** We accept that we are running in a shared process space (within the container). We mitigate this by using strict timeouts and memory limits on the Service.

### 3. Security: Trust gVisor (Reject eBPF)
**Decision:** Rely on Cloud Run's native gVisor sandbox instead of migrating to GKE Standard for eBPF (Tetragon).

*   **Reasoning:**
    *   **Complexity:** Implementing eBPF requires managing a GKE cluster with elevated privileges, significantly increasing operational overhead compared to serverless Cloud Run.
    *   **Redundancy:** Cloud Run uses gVisor, a user-space kernel that already intercepts and sanitizes syscalls, providing a robust sandbox that isolates the container from the host kernel.
    *   **Network Security:** Instead of eBPF egress filtering, we utilize Cloud Run VPC Service Controls and Egress Rules to prevent data exfiltration.

## Architecture Comparison

| Feature | Architecture I (Current) | Architecture II (New Target) | Benefit |
| :--- | :--- | :--- | :--- |
| **Policy Engine** | OPA Server (HTTP Sidecar) | `opa-wasm` (In-Process) | **95% Latency Reduction** (<1ms vs 20ms) |
| **Transport** | TCP Loopback (localhost:8181) | RAM (Function Call) | Eliminates serialization overhead |
| **Isolation** | Container (RunC/gVisor) | Container (gVisor) | Unchanged (High Security) |
| **Deployment** | Multi-Container Service | Single-Container Service | Simplified `service.yaml` |

## Migration Plan

1.  **Refactor Client:** The `OPAClient` in `src/governance/client.py` will be rewritten to load `policy.wasm` and execute `opa_wasm.OPAPolicy.evaluate()`.
2.  **Build Pipeline:** A new build step is required to compile `policies/*.rego` into `policy.wasm`.
3.  **Cleanup:** The sidecar definition in `deployment/service.yaml` and `opa_config.yaml` will be removed.

## Conclusion

Architecture II represents the optimal balance for this project. It maximizes performance by eliminating network hops while maintaining a strong security posture through Google's managed serverless infrastructure (gVisor).
