## 2025-05-19 - [The Cost of Cleanliness]
**Learning:** Instantiating `httpx.AsyncClient` inside a hot loop (or per-request) costs ~0.16ms even if the underlying transport is reused. This adds up in high-throughput gateways.
**Action:** Always instantiate `httpx.AsyncClient` (and `Client`) as a singleton or long-lived instance in `__init__`, reusing the transport and connection pool efficiently.
