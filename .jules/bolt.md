## 2025-05-23 - OPAClient Optimization
**Learning:** `httpx.AsyncClient` instantiation is expensive (~1.4ms per call) and defeats connection pooling if done per-request. Persistent clients are essential for high-throughput internal services.
**Action:** Always check for `async with httpx.AsyncClient()` inside hot loops. Prefer instantiating clients in `__init__` and reusing them.

## 2025-05-23 - Testing Persistent Clients with respx
**Learning:** When testing classes with persistent `httpx` clients, `respx` mocks must be active *before* the client is instantiated (or the client must be instantiated inside the `respx.mock` context). Fixtures that create clients outside the test function will bypass the mock if the client is created at import or fixture time.
**Action:** Instantiate service classes inside the test function or use `respx` fixtures that patch globally if possible, but explicit instantiation inside the mock context is safer.
