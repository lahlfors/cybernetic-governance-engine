# Neuro-Symbolic Governance: RBC and OPC

This document details the Neuro-Symbolic Governance architecture of the Financial Advisor system, focusing on the integration of **Residual-Based Control (RBC)** and **Optimization-Based Control (OPC)** within the `SymbolicGovernor`.

## 1. Overview

The system employs a multi-layered governance strategy to ensure safety and compliance in an autonomous agent environment. This strategy combines fast, deterministic safety checks with comprehensive policy evaluation.

| Governance Layer | Control Theory Concept | Implementation Component | Characteristics |
| :--- | :--- | :--- | :--- |
| **Layer 1: Safety** | **Residual-Based Control (RBC)** | `ControlBarrierFunction` (CBF) | **Fast**, Local, State-Based, Deterministic |
| **Layer 2: Policy** | **Optimization-Based Control (OPC)** | `OPAClient` (Open Policy Agent) | **Global**, Context-Aware, Policy-Based |
| **Layer 3: Oversight** | **Consensus / Human-in-the-Loop** | `ConsensusEngine` | **Adaptive**, High-Stakes, Multi-Agent Debate |

## 2. Residual-Based Control (RBC): The Safety Filter

**Residual-Based Control** focuses on maintaining the system within a safe operating region by monitoring the "residual" (difference) between the current state and the safety boundary.

### Implementation: Control Barrier Functions (CBF)
*   **Component:** `src/governed_financial_advisor/governance/safety.py`
*   **Logic:** The system uses a discrete-time Control Barrier Function ($h(x)$) to enforce safety constraints, such as maintaining a minimum cash balance.
*   **Formula:** $h(x_{next}) \ge (1 - \gamma) h(x_{current})$
    *   Where $h(x) = x - x_{safe}$
    *   $\gamma$ is the decay rate.
*   **Mechanism:**
    1.  Fetch the current state (e.g., cash balance) from Redis.
    2.  Calculate the proposed next state based on the action (e.g., trade amount).
    3.  Verify if the transition satisfies the barrier condition.
    4.  **Block** the action immediately if the condition is violated.

**Why RBC First?**
RBC is a **low-latency** check (~1-2ms) that relies only on local state. It acts as a "reflex" to prevent immediate catastrophic failures (e.g., bankruptcy) before expensive policy checks are performed.

## 3. Optimization-Based Control (OPC): The Policy Engine

**Optimization-Based Control** involves evaluating actions against a set of optimization criteria or policies to determine the optimal (or permissible) control input.

### Implementation: Open Policy Agent (OPA)
*   **Component:** `src/gateway/core/policy.py`
*   **Logic:** The system delegates complex, high-level policy decisions to OPA. Policies are defined in Rego and can reason about global context, user attributes, and regulatory requirements (e.g., "No trading in restricted regions").
*   **Mechanism:**
    1.  Construct a query payload with the action and its parameters.
    2.  Send the payload to the OPA service (HTTP/UDS).
    3.  OPA evaluates the policies and returns `ALLOW`, `DENY`, or `MANUAL_REVIEW`.

**Role in Hierarchy:**
OPC serves as the "Deliberative" layer. It is computationally more expensive (~10-50ms) than RBC but handles the complexity of organizational rules that cannot be captured by simple state equations.

## 4. Consensus: Adaptive Compute

For high-stakes decisions (e.g., large trade volumes), the system escalates to a **Consensus** mechanism.

### Implementation: Multi-Agent Debate
*   **Component:** `src/governed_financial_advisor/governance/consensus.py`
*   **Logic:** Multiple LLM-based critics ("Risk Manager", "Compliance Officer") review the proposed action.
*   **Outcome:** If the critics disagree or reject the action, it is blocked or escalated for human review.

## 5. Execution Flow in `SymbolicGovernor`

The `SymbolicGovernor` orchestrates these checks in a specific order to optimize for latency and safety ("Latency as Currency"):

1.  **RBC (Safety Filter):** Fail fast if the action is physically unsafe.
2.  **OPC (OPA Policy):** Check compliance with organizational rules.
3.  **Consensus:** Trigger heavy-weight review only if necessary.

```python
# Pseudo-code representation of src/gateway/governance/symbolic_governor.py

async def govern(tool_name, params):
    # 1. RBC: Fast Safety Check
    if not safety_filter.verify_action(tool_name, params):
        raise GovernanceError("Safety Violation (RBC)")

    # 2. OPC: Policy Check
    if not await opa_client.evaluate_policy(tool_name, params):
        raise GovernanceError("Policy Violation (OPC)")

    # 3. Consensus: High-Stakes Review
    if requires_consensus(tool_name, params):
        if not await consensus_engine.check_consensus(tool_name, params):
            raise GovernanceError("Consensus Failed")
```
