## 2024-05-23 - Reuse httpx.AsyncClient in Daemon Services
**Learning:** `OPAClient` was instantiating a new `httpx.AsyncClient` for every policy check. In a high-frequency path (every tool execution), this adds significant overhead (SSL/TCP handshake).
**Action:** Always initialize `httpx.AsyncClient` in `__init__` for long-lived services (like `GatewayService` components) to enable connection pooling.
