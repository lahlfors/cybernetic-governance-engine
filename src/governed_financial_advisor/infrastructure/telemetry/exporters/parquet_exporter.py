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

    def __init__(
        self,
        gcs_bucket: str | None = None,
        gcs_prefix: str = "cold_tier",
        local_fallback_path: str = "logs/cold_tier",
    ):
        import os
        self.gcs_bucket = gcs_bucket or os.getenv("COLD_TIER_GCS_BUCKET")
        self.gcs_prefix = os.getenv("COLD_TIER_GCS_PREFIX", gcs_prefix)
        self.local_fallback_path = Path(local_fallback_path)
        self._gcs_client = None
        self._gcs_available = False

        # Initialize GCS client if bucket is configured
        if self.gcs_bucket:
            try:
                from google.cloud import storage
                self._gcs_client = storage.Client()
                # Verify bucket exists (optional, but good for fail-fast)
                # self._gcs_client.get_bucket(self.gcs_bucket) 
                self._gcs_available = True
                logger.info(f"GCS cold tier storage initialized: gs://{self.gcs_bucket}/{self.gcs_prefix}/")
            except Exception as e:
                logger.warning(f"GCS unavailable, falling back to local storage: {e}")
                self._gcs_available = False

        # Ensure local fallback directory exists
        if not self._gcs_available:
            self.local_fallback_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Using local cold tier storage: {self.local_fallback_path}")

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        try:
            data_list = []
            for span in spans:
                data = self._span_to_dict(span)
                data_list.append(data)

            if not data_list:
                return SpanExportResult.SUCCESS

            df = pd.DataFrame(data_list)
            
            # Generate date-partitioned path and filename
            # Structure: YYYY/MM/DD/batch_<timestamp>_<count>.parquet
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            date_partition = now.strftime("%Y/%m/%d")
            timestamp = int(time.time() * 1000)
            filename = f"batch_{timestamp}_{len(data_list)}_spans.parquet"

            if self._gcs_available:
                return self._export_to_gcs(df, date_partition, filename)
            else:
                return self._export_to_local(df, date_partition, filename)

        except Exception as e:
            logger.error(f"Failed to export spans to Parquet: {e}")
            return SpanExportResult.FAILURE

    def _export_to_gcs(self, df: pd.DataFrame, date_partition: str, filename: str) -> SpanExportResult:
        """Write Parquet to GCS with date-partitioned path."""
        try:
            import tempfile
            import os
            # Write to temp file first
            with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
                df.to_parquet(tmp.name, engine="pyarrow")
                tmp_path = tmp.name

            # Upload to GCS
            gcs_path = f"{self.gcs_prefix}/{date_partition}/{filename}"
            bucket = self._gcs_client.bucket(self.gcs_bucket)
            blob = bucket.blob(gcs_path)
            blob.upload_from_filename(tmp_path)

            # Cleanup temp file
            os.unlink(tmp_path)

            logger.debug(f"Exported {df.shape[0]} spans to gs://{self.gcs_bucket}/{gcs_path}")
            return SpanExportResult.SUCCESS

        except Exception as e:
            logger.error(f"GCS upload failed: {e}")
            # Try local fallback on GCS failure
            return self._export_to_local(df, date_partition, filename)

    def _export_to_local(self, df: pd.DataFrame, date_partition: str, filename: str) -> SpanExportResult:
        """Write Parquet to local disk with date-partitioned path."""
        try:
            local_dir = self.local_fallback_path / date_partition
            local_dir.mkdir(parents=True, exist_ok=True)
            filepath = local_dir / filename

            df.to_parquet(filepath, engine="pyarrow")

            logger.debug(f"Exported {df.shape[0]} spans to {filepath}")
            return SpanExportResult.SUCCESS

        except Exception as e:
            logger.error(f"Local export failed: {e}")
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
