## 2026-01-28 - [httpx Client Reuse vs Transport Reuse]
**Learning:** Initializing `httpx.AsyncClient` is expensive (~40ms), but initializing it with an *existing* transport is extremely cheap (~0.07ms). However, to fully leverage connection pooling (keep-alive), it's cleaner and more standard to reuse the `AsyncClient` instance itself rather than just the transport, as the client manages the high-level session state.
**Action:** Always prefer instantiating `httpx.AsyncClient` once as a long-lived object (singleton or service member) rather than creating it per-request, even if passing a transport.

## 2026-01-28 - [Double JSON Serialization in Telemetry]
**Learning:** A common pattern in this codebase is `len(json.dumps(data))` for telemetry followed by `client.post(json=data)`. This forces two serialization passes.
**Action:** Serialize once to string, measure length, and pass `content=serialized_string` with appropriate headers.
