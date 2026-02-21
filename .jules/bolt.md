## 2025-02-12 - Persistent HTTP Clients
**Learning:** Instantiating `httpx.AsyncClient` inside a hot path (e.g., every chat request) incurs massive overhead (TCP/SSL handshake).
**Action:** Always instantiate `httpx.AsyncClient` once (singleton or globally) and reuse it for the application lifecycle. Use `lifespan` events in FastAPI to close it gracefully.

## 2025-02-12 - Python Async Tool Shadowing
**Learning:** Defining an async wrapper function with the same name as an imported synchronous function (e.g., `async def get_market_data` wrapping `from ... import get_market_data`) causes infinite recursion if the wrapper calls the function by name, because the local function name shadows the import.
**Action:** Always alias imported functions when wrapping them (e.g., `from ... import get_market_data as get_market_data_impl`) to avoid shadowing and recursion bugs.
