## 2025-02-17 - httpx.AsyncClient Instantiation Overhead
**Learning:** Instantiating `httpx.AsyncClient` inside a request loop (e.g., `async with httpx.AsyncClient():`) incurs a massive overhead (~43ms per call) due to SSL context loading and other setups. Reusing the client reduces this to ~0.03ms.
**Action:** Always prefer persistent `httpx.AsyncClient` instances for high-throughput services, especially within Singletons or dependency injection containers. Use `aclose()` for cleanup.
