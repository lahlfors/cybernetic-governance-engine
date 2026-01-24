# Current Architecture Improvements: Optimization Plan

**Status:** DRAFT
**Context:** Analysis of "Low-Hanging Fruit" optimizations for the current Hybrid (LangGraph + ADK) architecture.
**Goal:** Improve Latency, Reliability, and Testability without a full platform migration.

---

## 1. Governance Latency: The Blocking I/O Bottleneck

### The Problem
The `OPAClient` in `src/governance/client.py` utilizes the synchronous `requests` library.
```python
response = requests.post(self.url, json=..., timeout=1.0)
```
While `src/graph/nodes/optimistic_nodes.py` attempts to mitigate this by wrapping the call in `asyncio.to_thread`, this is an inefficient use of the thread pool for I/O bound tasks. It consumes a thread for every concurrent governance check, limiting scalability under load.

### The Remediation: Native Async Client
Migrate `OPAClient` to use `httpx.AsyncClient`.

**Benefit:**
*   **True Concurrency:** Allows the event loop to manage thousands of pending OPA checks without thread exhaustion.
*   **Simplified Optimistic Logic:** Removes the need for `asyncio.to_thread` wrappers in the orchestration layer.

```python
# Proposed Interface
async with httpx.AsyncClient() as client:
    response = await client.post(self.url, json=...)
```

---

## 2. Dependency Injection & Testability

### The Problem
`src/graph/nodes/adapters.py` imports instantiated agent objects directly from module scope:
```python
from src.agents.data_analyst.agent import data_analyst_agent
```
This "Global State" pattern makes unit testing difficult:
1.  **Pollution:** Tests share the same agent instance state.
2.  **Mocking Difficulty:** Requires complex `unittest.mock.patch` calls to replace the global instance.
3.  **Initialization Side Effects:** Importing the module triggers agent initialization (which may try to connect to Vertex AI).

### The Remediation: Factory Pattern
Refactor agent definitions to export a `create_agent()` factory function instead of a global instance.

```python
# src/agents/data_analyst/agent.py
def create_data_analyst(config: AgentConfig) -> Agent:
    return Agent(...)

# src/graph/nodes/adapters.py
def data_analyst_node(state):
    agent = create_data_analyst(current_config) # Created on demand or retrieved from DI container
    ...
```

---

## 3. Resilience: Circuit Breakers for Policy Engine

### The Problem
The current `OPAClient` implements a "Fail Closed" mechanism (catch Exception -> return DENY). While secure, it lacks a "Circuit Breaker."
If the OPA Sidecar is overwhelmed or down, the application will continue to hammer it with requests until timeouts occur (1.0s per request). This causes a cascading latency failure for the user.

### The Remediation: Soft Fallback
Implement a Circuit Breaker (e.g., using `tenacity` or custom logic):
1.  **Threshold:** If 5 consecutive requests fail/timeout.
2.  **Open State:** Stop calling OPA for 30 seconds.
3.  **Fallback:**
    *   **Strict Mode:** Fail fast (Instant DENY, no timeout).
    *   **Degraded Mode:** Allow "Safe Harbor" actions (read-only), block "Write" actions.

---

## 4. Observability: Structured Logging

### The Problem
The current nodes use `print("--- [Graph] Calling ... ---")` for observability.
This is insufficient for production debugging in Cloud Logging.

### The Remediation: Canonical JSON Logging
Replace all `print` statements with a structured logger that injects the `trace_id`.

```python
logger.info("node_execution_start", extra={
    "node": "data_analyst",
    "trace_id": state.get("trace_id"),
    "user_id": state.get("user_id")
})
```

---

## 5. Summary of Priority

| Improvement | Effort | Impact | Priority |
| :--- | :--- | :--- | :--- |
| **Async OPA Client** | Low | High (Latency) | **P0** |
| **Dependency Injection** | Medium | Medium (DevEx) | **P1** |
| **Circuit Breaker** | Medium | High (Resilience) | **P1** |
| **Structured Logging** | Low | High (Ops) | **P0** |
