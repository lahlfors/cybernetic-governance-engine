from typing import Callable, Optional, Any, Dict
from opentelemetry.sdk.trace import SpanProcessor, ReadableSpan
from opentelemetry.context import Context

class StrippedSpan:
    """
    A proxy wrapper for ReadableSpan that masks heavy attributes.
    This allows downstream processors (Hot Tier) to see a lightweight version
    without mutating the original span (which Cold Tier needs).
    """
    def __init__(self, span: ReadableSpan, heavy_attributes: set):
        self._span = span
        self._heavy_attributes = heavy_attributes
        self._filtered_attributes = None

    def __getattr__(self, name: str) -> Any:
        # Delegate everything else to the original span
        return getattr(self._span, name)

    @property
    def attributes(self) -> Dict[str, Any]:
        """Return attributes excluding the heavy ones."""
        if self._filtered_attributes is None:
            original_attrs = self._span.attributes or {}
            self._filtered_attributes = {
                k: v for k, v in original_attrs.items()
                if k not in self._heavy_attributes
            }
        return self._filtered_attributes

class GenAICostOptimizerProcessor(SpanProcessor):
    """
    A SpanProcessor that implements 'Tiered Observability' for GenAI.

    It routes spans to two tiers:
    1. Cold Tier: Receives full-fidelity spans (based on sampling rule).
    2. Hot Tier: Receives stripped, lightweight spans (always).

    This uses a 'Delegation Pattern' where it delegates to other SpanProcessors,
    allowing for efficient batching and async processing in both tiers.
    """

    def __init__(
        self,
        hot_processor: SpanProcessor,
        cold_processor: SpanProcessor,
        pricing_rule: Callable[[ReadableSpan], bool]
    ):
        self.hot_processor = hot_processor
        self.cold_processor = cold_processor
        self.pricing_rule = pricing_rule

        # Default heavy attributes to strip
        self.heavy_attributes = {
            "gen_ai.content.prompt",
            "gen_ai.content.completion",
            "reasoning_trace",
            "RAG_chunks",
            "risk_feedback"
        }

    def on_start(self, span: Any, parent_context: Optional[Context] = None) -> None:
        # Forward on_start to both processors
        self.cold_processor.on_start(span, parent_context)
        self.hot_processor.on_start(span, parent_context)

    def on_end(self, span: ReadableSpan) -> None:
        """
        Called when a span ends.
        Routes the span to Cold and Hot tiers.
        """
        # 1. Cold Tier: Check if we should pay for storage
        if self.pricing_rule(span):
            # Send full fidelity span
            self.cold_processor.on_end(span)

        # 2. Hot Tier: Always send, but strip heavy attributes
        # We create a proxy to avoid mutating the original span
        stripped_span = StrippedSpan(span, self.heavy_attributes)
        self.hot_processor.on_end(stripped_span)

    def shutdown(self) -> None:
        self.cold_processor.shutdown()
        self.hot_processor.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        f1 = self.cold_processor.force_flush(timeout_millis)
        f2 = self.hot_processor.force_flush(timeout_millis)
        return f1 and f2
