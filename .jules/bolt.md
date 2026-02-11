## 2025-02-12 - Persistent HTTP Clients
**Learning:** Instantiating `httpx.AsyncClient` inside a hot path (e.g., every chat request) incurs massive overhead (TCP/SSL handshake).
**Action:** Always instantiate `httpx.AsyncClient` once (singleton or globally) and reuse it for the application lifecycle. Use `lifespan` events in FastAPI to close it gracefully.

## 2025-05-21 - gRPC Resource Cleanup
**Learning:** Python gRPC servers () lack a native lifespan context manager.
**Action:** Wrap `server.wait_for_termination()` in a `try...finally` block to ensure resources (like persistent HTTP clients) are closed gracefully on shutdown.

## 2025-05-21 - gRPC Resource Cleanup
**Learning:** Python gRPC servers (`grpc.aio.server`) lack a native lifespan context manager.
**Action:** Wrap `server.wait_for_termination()` in a `try...finally` block to ensure resources (like persistent HTTP clients) are closed gracefully on shutdown.
