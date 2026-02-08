## 2025-05-15 - OPAClient Connection Pooling
**Learning:** The OPAClient was creating a new `httpx.AsyncClient` for every single policy evaluation request. This defeats connection pooling and adds significant overhead (TLS handshakes, etc.) to the governance path.
**Action:** When working with HTTP clients in this codebase, always verify if they are long-lived and reused. Refactored `OPAClient` to persist the client instance.
