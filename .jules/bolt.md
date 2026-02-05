## 2025-02-19 - HTTP Client Reuse
**Learning:** Instantiating `httpx.AsyncClient` inside a hot path (like `chat`) incurs significant latency (46ms vs 4ms on localhost) due to connection establishment overhead. Always use a persistent client instance for frequent internal service calls.
**Action:** Check for `async with httpx.AsyncClient()` inside loops or frequent function calls and refactor to use a shared instance.
