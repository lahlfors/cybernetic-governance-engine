## 2024-05-22 - [Optimization] OPAClient Connection Pooling
**Learning:** Instantiating `httpx.AsyncClient` inside hot loops causes significant overhead (~40ms per call) due to SSL context creation and connection setup.
**Action:** Use lazy initialization and reuse the client instance to enable connection pooling.
