## 2025-02-12 - Persistent HTTP Clients
**Learning:** Instantiating `httpx.AsyncClient` inside a hot path (e.g., every chat request) incurs massive overhead (TCP/SSL handshake).
**Action:** Always instantiate `httpx.AsyncClient` once (singleton or globally) and reuse it for the application lifecycle. Use `lifespan` events in FastAPI to close it gracefully.
