# [Proposal] GenAICostOptimizerProcessor: Tiered export for large LLM payloads

## Problem Description
With the rise of GenAI, spans are becoming exponentially larger due to `gen_ai.content.prompt` and `gen_ai.content.completion` attributes. A single trace can easily exceed 50kb.

**The Problem:** Users want operational metrics (latency, token counts, error codes) in "Hot Storage" (e.g., Jaeger, Datadog) but cannot afford to store the full text payloads there.

**The Need:** However, for compliance (ISO 42001, EU AI Act), they must retain the full prompts/responses in "Cold Storage" (e.g., S3/Parquet) for auditability.

Currently, there is no standard `SpanProcessor` that supports this "Fork and Strip" logic based on GenAI Semantic Conventions.

## Proposed Solution
I propose adding a `GenAICostOptimizerProcessor` to the contrib package.

This processor acts as a router and modifier, implementing a "Delegation Pattern":

```python
class GenAICostOptimizerProcessor(SpanProcessor):
    def __init__(
        self,
        hot_processor: SpanProcessor,
        cold_processor: SpanProcessor,
        pricing_rule: Callable[[Span], bool]
    ):
        ...
```

It performs the following logic on `on_end(span)`:
1.  **Cold Tier Delegation**: It evaluates the `pricing_rule` (e.g., "Keep 100% of Write spans, 1% of Chat spans"). If true, it delegates the **full fidelity** span to the `cold_processor`.
2.  **Hot Tier Stripping**: It creates a lightweight `StrippedSpan` proxy that masks heavy attributes (like `gen_ai.content.*`) and delegates this proxy to the `hot_processor`.

### Architecture
This design avoids the common pitfall of blocking I/O by accepting `SpanProcessor` instances rather than `SpanExporter` instances. This allows users to wrap their exporters in `BatchSpanProcessor`, ensuring that both the Hot and Cold tiers operate asynchronously and efficiently.

**Flow:**
App -> `GenAICostOptimizerProcessor`
   |-> (Full Span) -> `BatchSpanProcessor` -> `ParquetExporter` (Cold)
   |-> (Stripped Span) -> `BatchSpanProcessor` -> `OTLPSpanExporter` (Hot)

## Alternatives Considered
*   **Collector-side filtering:** This is possible but inefficient. It requires sending the full 50kb payload over the network to the Collector just to drop it. Doing it in the SDK (Application side) saves egress bandwidth.
*   **Custom Implementation:** I have implemented this locally using a custom `SpanProcessor`, and it drastically reduced observability costs while maintaining compliance. I believe this pattern is common enough to warrant inclusion in the library.

## Additional Context
I have a working prototype of this logic that handles attribute stripping (via a proxy to ensure immutability for the Cold tier) and simple heuristic sampling. I would be happy to open a PR if this aligns with the project's roadmap.
