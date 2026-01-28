import logging
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pandas as pd
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

logger = logging.getLogger(__name__)

class ParquetSpanExporter(SpanExporter):
    """
    Exports spans to local Parquet files.
    Each export batch is written to a new file to support asynchronous ingestion.
    """

    def __init__(self, output_path: str = "logs/cold_tier"):
        self.output_path = Path(output_path)
        self.output_path.mkdir(parents=True, exist_ok=True)

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        try:
            data_list = []
            for span in spans:
                data = self._span_to_dict(span)
                data_list.append(data)

            if not data_list:
                return SpanExportResult.SUCCESS

            df = pd.DataFrame(data_list)

            # Generate a unique filename for this batch
            # We use the first span's trace/span IDs for uniqueness in the name,
            # or just a timestamp if batch is large.
            # The original logic used trace_id_span_id_timestamp.parquet per span.
            # Since we receive a batch, we'll use a batch timestamp.
            timestamp = int(time.time() * 1000)

            # To maintain compatibility with the previous file naming convention which
            # helped with debugging (trace_id in filename), we can try to use the first span's trace ID
            # if the batch is small or just use a generic batch name.
            # However, the previous logic wrote one file per span (implied by the file naming).
            # SpanExporter receives a BATCH.
            # If we want to strictly replicate "one file per span" (which is inefficient but what the code did),
            # we would iterate. But writing one parquet file per span is very bad for I/O.
            # A 'Batch' exporter should write a 'Batch' file.
            # Let's write one file per export call.

            filename = f"batch_{timestamp}_{len(data_list)}_spans.parquet"
            filepath = self.output_path / filename

            # Write to Parquet
            df.to_parquet(filepath, engine="pyarrow")

            return SpanExportResult.SUCCESS

        except Exception as e:
            logger.error(f"Failed to export spans to Parquet: {e}")
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        """Cleanup logic if needed."""
        pass

    def _span_to_dict(self, span: ReadableSpan) -> dict[str, Any]:
        """Converts a ReadableSpan to a dictionary suitable for DataFrame."""
        trace_id = f"{span.context.trace_id:032x}"
        span_id = f"{span.context.span_id:016x}"

        data = {
            "trace_id": trace_id,
            "span_id": span_id,
            "name": span.name,
            "start_time": span.start_time,
            "end_time": span.end_time,
            "status_code": str(span.status.status_code),
        }

        # Merge attributes with prefix
        # We handle attributes carefully
        attributes = span.attributes or {}
        for k, v in attributes.items():
            data[f"attr.{k}"] = str(v)  # Convert to string for schema consistency

        return data
