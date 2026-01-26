## 2025-05-22 - Optimistic Parallelism for Governance
**Learning:** In LLM agents with governance sidecars (NeMo/OPA), sequential checks add significant latency. "Optimistic Execution" shouldn't just be a graph node pattern—it can be applied at the request entry point.
**Action:** When integrating governance checks, verify if they can run concurrently with the main "happy path" logic (e.g., plan generation), cancelling the main path only if governance fails ("Fail Fast"). Using `asyncio.create_task` + `cancel()` is a simple, powerful pattern for this.
