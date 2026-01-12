import os
import logging
import random
import time
from typing import Any, Dict
from opentelemetry.sdk.trace import SpanProcessor, ReadableSpan
import pandas as pd
from pathlib import Path

logger = logging.getLogger("TieredObservability")

class TieredSpanProcessor(SpanProcessor):
    """
    Implements 'Tiered Observability' logic:
    1. 'Cold Tier': Selectively writes full span payloads to local Parquet files.
    2. 'Hot Tier': Strips heavy attributes from the span before it proceeds to Hot exporters.

    Sampling Logic:
    - WRITE (Tools/Execution): 100%
    - RISKY (Blocked/Altered): 100%
    - READ (Chat): 1%
    """

    def __init__(self, cold_tier_path: str = "logs/cold_tier"):
        self.cold_tier_path = Path(cold_tier_path)
        self.cold_tier_path.mkdir(parents=True, exist_ok=True)

        # Heavy attributes to strip for Hot Tier
        self.heavy_attributes = {
            "gen_ai.content.prompt",
            "gen_ai.content.completion",
            "reasoning_trace",
            "RAG_chunks",
            "risk_feedback" # Often verbose
        }

    def on_start(self, span: Any, parent_context: Any = None) -> None:
        pass

    def on_end(self, span: ReadableSpan) -> None:
        """
        Called when a span ends.
        We analyze attributes to decide on Cold Tier storage,
        then strip attributes for Hot Tier.
        """
        try:
            # 1. Capture full attributes (Snapshot)
            # span.attributes is a simpler dict-like view in ReadableSpan
            # We explicitly copy it because we are about to modify the span.
            # Using span._attributes directly to ensure we get everything if span.attributes is immutable-ish (though usually it's just a property)
            # In SDK, span.attributes returns MappingProxyType or similar.
            # We access _attributes for raw access if needed, but for reading, .attributes is fine.
            attributes = dict(span.attributes) if span.attributes else {}

            # 2. Determine Sampling
            should_sample = self._should_sample(span, attributes)

            # 3. Write to Cold Tier if sampled
            if should_sample:
                self._write_to_cold_tier(span, attributes)

            # 4. Strip Heavy Attributes for Hot Tier (In-Place Modification)
            # This affects subsequent processors (like BatchSpanProcessor -> CloudTrace)
            if hasattr(span, "_attributes"):
                for key in self.heavy_attributes:
                    if key in span._attributes:
                        del span._attributes[key]
            else:
                logger.warning("Could not strip attributes: span has no _attributes")

        except Exception as e:
            logger.error(f"Error in TieredSpanProcessor: {e}")

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True

    def _should_sample(self, span: ReadableSpan, attributes: Dict[str, Any]) -> bool:
        """
        Applies Semantic Sampling Logic.
        """
        # A. RISKY: Guardrail intervention (BLOCKED or ALTERED)
        outcome = attributes.get("guardrail.outcome")
        if outcome in ["BLOCKED", "ALTERED"]:
            return True

        # B. WRITE: Tool execution
        # Check for 'gen_ai.tool.name' or if span name implies execution
        if "gen_ai.tool.name" in attributes:
            return True

        # Heuristic for write nodes if not explicitly using tool attribute
        if "execute" in span.name.lower() or "write" in span.name.lower():
            return True

        # C. READ: Default (Chat) -> 1%
        # We assume if it's not Write/Risky, it's Read/Chat
        if random.random() < 0.01:
            return True

        return False

    def _write_to_cold_tier(self, span: ReadableSpan, attributes: Dict[str, Any]):
        """
        Writes the span data to a Parquet file.
        """
        try:
            trace_id = f"{span.context.trace_id:032x}"
            span_id = f"{span.context.span_id:016x}"
            timestamp = int(time.time() * 1000)

            # Flatten data for DataFrame
            data = {
                "trace_id": trace_id,
                "span_id": span_id,
                "name": span.name,
                "start_time": span.start_time,
                "end_time": span.end_time,
                "status_code": str(span.status.status_code),
            }

            # Merge attributes
            # We prefix attributes to avoid collision
            for k, v in attributes.items():
                data[f"attr.{k}"] = str(v) # Convert to string to ensure Parquet compatibility for mixed types

            df = pd.DataFrame([data])

            filename = f"trace_{trace_id}_{timestamp}.parquet"
            filepath = self.cold_tier_path / filename

            # Write to Parquet
            df.to_parquet(filepath, engine="pyarrow")
            # logger.info(f"❄️ Cold Tier: Written trace {trace_id} to {filepath}")

        except Exception as e:
            logger.error(f"Failed to write to cold tier: {e}")
