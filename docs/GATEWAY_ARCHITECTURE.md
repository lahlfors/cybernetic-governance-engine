# Gateway Architecture & API (Sovereign Engine)

## Overview

The **Gateway Service** (`src/gateway/server/main.py`) acts as the "Central Nervous System" of the Sovereign Financial Advisor. It is a high-performance gRPC service that mediates all interactions between Agents (the "Brain") and the external world (Markets, Databases, Tools).

It enforces strict governance policies at the infrastructure level, ensuring that no agent can bypass safety controls.

---

## Sovereign Architecture: Split-Brain vLLM

The Gateway implements a **Split-Brain Topology** to optimize for both deep reasoning and fast governance.

### 1. Node A: The Brain (Reasoning Plane)
*   **Service:** `vllm-reasoning`
*   **Model:** `meta-llama/Meta-Llama-3.1-8B-Instruct`
*   **Role:** Handles complex tasks requiring Chain-of-Thought (CoT), planning, and data analysis.
*   **Routing:** Accessed when `mode="reasoning"`, `mode="planner"`, or `mode="analysis"`.

### 2. Node B: The Police (Governance Plane)
*   **Service:** `vllm-governance`
*   **Model:** `meta-llama/Llama-3.2-3B-Instruct`
*   **Role:** Handles fast, constrained tasks like FSM checks, JSON schema validation, and chat.
*   **Routing:** Accessed when `mode="chat"`, `mode="verifier"`, or `mode="json_schema"`.

### GatewayClient
The `GatewayClient` (`src/gateway/core/llm.py`) abstracts this complexity from the application. It automatically routes requests to the correct vLLM node based on the `mode` parameter.

```python
# Automatic Routing
client.generate(prompt="...", mode="reasoning") # -> vllm-reasoning
client.generate(prompt="...", mode="chat")      # -> vllm-governance
```

---

## Core Responsibilities

1.  **Tool Execution & Governance:**
    *   Receives tool calls from agents.
    *   Routes them through the **Symbolic Governor**.
    *   Executes the tool only if all checks pass.

2.  **LLM Proxy:**
    *   Proxies requests to the appropriate vLLM node (Reasoning vs. Governance).
    *   Injects system prompts and context.

3.  **Safety Enforcement (The "Immune System"):**
    *   Manages the **Redis Interrupt** mechanism for parallel execution.
    *   Exposes meta-tools for safety validation (`check_safety_constraints`).

---

## API Reference (gRPC)

### Service: `Gateway`

#### `ExecuteTool(ToolRequest) -> ToolResponse`
Executes a specific capability.

*   **Request:**
    *   `tool_name`: String (e.g., `execute_trade`, `check_market_status`)
    *   `params_json`: JSON String of arguments.

*   **Response:**
    *   `status`: `SUCCESS`, `BLOCKED`, `ERROR`
    *   `output`: Result string or error message.

#### Supported Tools

| Tool Name | Description | Governance Checks |
| :--- | :--- | :--- |
| `execute_trade` | Executes a financial transaction via Broker API. | **Full:** STPA, OPA, CBF, SR 11-7, Redis Interrupt |
| `execute_python_analysis` | **Computer Use**: Executes Python code in the Sandbox Sidecar. | **Restricted:** Sandboxed Container. |
| `check_market_status` | Fetches market data. | **Light:** Basic validation. |
| `verify_content_safety` | Checks text via NeMo Guardrails. | **NeMo:** Semantic checks. |
| `check_safety_constraints` | **Meta-Tool**: Runs a dry-run of the Governor on a proposed action. Used by Evaluator. | **Full (Dry Run)** |
| `trigger_safety_intervention` | **Meta-Tool**: Sets the global `safety_violation` flag to stop execution. | **Audit Log Only** |

---

## Neuro-Symbolic Integration

The Gateway integrates the `SymbolicGovernor` which orchestrates:
*   **OPA Client:** Policy checks.
*   **Safety Filter:** Control Barrier Functions (CBF).
*   **Consensus Engine:** Multi-agent agreement.
*   **STPA Validator:** Deterministic UCA checks.

## Telemetry

All Gateway actions are traced via OpenTelemetry with semantic conventions for GenAI (Module 4). Spans include:
*   `genai.tool.name`
*   `governance.verdict`
*   `safety.violation.reason`
