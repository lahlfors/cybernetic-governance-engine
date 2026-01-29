# Bolt's Journal

## 2024-05-24 - [Initial Setup]
**Learning:** Bolt journal initialized.
**Action:** Always check this file for past learnings before starting optimization tasks.

## 2024-05-24 - [Reusable HTTP Clients]
**Learning:** Creating `httpx.AsyncClient` inside a hot loop (or frequently called method) incurs massive overhead (~40ms/call). Reusing the client reduced latency by ~70x.
**Action:** Always check for `async with httpx.AsyncClient()` inside `evaluate_policy` or similar frequently called methods. Move client instantiation to `__init__`.
