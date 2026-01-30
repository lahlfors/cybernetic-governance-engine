## 2024-05-22 - [Optimizing OPA Client Connection Reuse]
**Learning:** Found that `OPAClient` was instantiating a new `httpx.AsyncClient` for every request inside `evaluate_policy`. This negates connection pooling (Keep-Alive) and adds significant TCP/SSL overhead (~15% even with mock transport).
**Action:** Always instantiate `httpx.AsyncClient` (or `aiohttp.ClientSession`) in `__init__` and reuse it. Ensure `transport` objects are also properly managed.
