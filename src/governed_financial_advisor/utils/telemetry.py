"""
Telemetry configuration for GCP Cloud Logging and Cloud Trace.
"""
import contextlib
import logging
import os
import random
import sys
import base64
from typing import Any

from pythonjsonlogger import jsonlogger


# Configure Structured JSON Logging immediately
class TraceIdFilter(logging.Filter):
    """Injects OpenTelemetry trace_id and span_id into log records."""
    def filter(self, record):
        try:
            from opentelemetry import trace
            span = trace.get_current_span()
            if span:
                ctx = span.get_span_context()
                if ctx.is_valid:
                    record.trace_id = format(ctx.trace_id, "032x")
                    record.span_id = format(ctx.span_id, "016x")
                    record.trace_sampled = ctx.trace_flags.sampled
        except ImportError:
            pass
        return True

def setup_canonical_logging():
    """Configures the root logger to output structured JSON with trace correlation."""
    root_logger = logging.getLogger()

    # Avoid duplicate handlers
    if root_logger.handlers:
        return

    logHandler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s %(trace_id)s %(span_id)s',
        rename_fields={'levelname': 'severity', 'asctime': 'timestamp'}
    )
    logHandler.setFormatter(formatter)
    logHandler.addFilter(TraceIdFilter())
    root_logger.addHandler(logHandler)
    root_logger.setLevel(logging.INFO)

# Initialize logging early
setup_canonical_logging()
logger = logging.getLogger("FinancialAdvisor")

_telemetry_configured = False

def smart_sampling(span: Any) -> bool:
    """
    Applies Semantic Sampling Logic for the Cold Tier.

    Logic:
    - RISKY (Blocked/Altered): 100%
    - WRITE (Tools/Execution): 100%
    - READ (Chat): 1%
    """
    attributes = span.attributes or {}

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

def configure_telemetry():
    """
    Configures OpenTelemetry tracing and Google Cloud Logging.
    This function is idempotent - calling it multiple times has no effect.
    """
    global _telemetry_configured
    if _telemetry_configured:
        return

    try:
        # Import optional dependencies
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        # Try to configure Google Cloud Trace
        try:
            from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter

            from src.infrastructure.telemetry.exporters.parquet_exporter import (
                ParquetSpanExporter,
            )
            from src.infrastructure.telemetry.processors.genai_cost_optimizer import (
                GenAICostOptimizerProcessor,
            )

            # Set up tracer provider
            provider = TracerProvider()
            trace.set_tracer_provider(provider)

            # 1. Define Exporters
            # Hot Tier: Cloud Trace
            cloud_exporter = CloudTraceSpanExporter()
            hot_processor = BatchSpanProcessor(cloud_exporter)

            # Cold Tier: Local Parquet
            parquet_exporter = ParquetSpanExporter()
            cold_processor = BatchSpanProcessor(parquet_exporter)

            # Langfuse Tier: OTLP
            langfuse_public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
            langfuse_secret_key = os.getenv("LANGFUSE_SECRET_KEY")
            langfuse_base_url = os.getenv("LANGFUSE_BASE_URL", "http://localhost:3000")

            if langfuse_public_key and langfuse_secret_key:
                auth_str = f"{langfuse_public_key}:{langfuse_secret_key}"
                auth_header = f"Basic {base64.b64encode(auth_str.encode()).decode()}"
                
                otlp_exporter = OTLPSpanExporter(
                    endpoint=f"{langfuse_base_url}/api/public/otel/v1/traces",
                    headers={"Authorization": auth_header}
                )
                otlp_processor = BatchSpanProcessor(otlp_exporter)
                provider.add_span_processor(otlp_processor)
                logger.info("✅ OpenTelemetry: Langfuse OTLP Exporter configured.")
            else:
                 logger.warning("⚠️ Langfuse credentials not found. Skipping OTLP export.")

            # 2. Configure Optimizer Processor
            optimizer = GenAICostOptimizerProcessor(
                hot_processor=hot_processor,
                cold_processor=cold_processor,
                pricing_rule=smart_sampling
            )

            # 3. Add to Provider
            provider.add_span_processor(optimizer)

            logger.info("✅ OpenTelemetry: Tiered Observability (Cost Optimizer) configured.")
            logger.info("✅ OpenTelemetry: Google Cloud Trace Exporter configured.")

            # Instrument the requests and httpx libraries for HTTP tracing
            try:
                from opentelemetry.instrumentation.requests import RequestsInstrumentor
                RequestsInstrumentor().instrument()
                logger.info("✅ OpenTelemetry: Requests HTTP library instrumented.")

                # Instrument httpx if available
                try:
                    from opentelemetry.instrumentation.httpx import (
                        HTTPXClientInstrumentor,
                    )
                    HTTPXClientInstrumentor().instrument()
                    logger.info("✅ OpenTelemetry: HTTPX library instrumented.")
                except ImportError:
                    pass

            except ImportError:
                logger.warning("⚠️ Requests/HTTPX instrumentation not available")
            except Exception as e:
                logger.warning(f"⚠️ HTTP instrumentation failed: {e}")

        except Exception as e:
            logger.warning(f"⚠️ OpenTelemetry Cloud Trace not configured: {e}")

        # Configure Google Cloud Logging (if explicitly needed, but JSON to stdout is often enough for Cloud Run)
        # We prefer our custom JSON handler for consistency, but if GCL client is used, it might attach its own handler.
        # We will wrap it in try-except but mostly rely on our setup_canonical_logging
        try:
            # Check environment to decide if we want to use the library
            if os.getenv("GOOGLE_CLOUD_PROJECT"):
                 pass
                 # We skip google.cloud.logging.Client().setup_logging() to avoid overriding our JSON formatter
                 # unless we want to use its specific features.
                 # For Phase 1/2, stdout JSON is best practice.
        except Exception as e:
             logger.warning(f"⚠️ Google Cloud Logging check failed: {e}")

        _telemetry_configured = True
        logger.info("✅ Telemetry configuration complete.")

    except ImportError as e:
        logger.warning(f"⚠️ Telemetry dependencies not available: {e}")
    except Exception as e:
        logger.error(f"❌ Telemetry configuration failed: {e}")


# Tracer for creating custom spans
def get_tracer():
    """Returns a tracer for creating custom spans."""
    try:
        from opentelemetry import trace
        return trace.get_tracer("src.genai")
    except ImportError:
        return None


@contextlib.contextmanager
def genai_span(name: str, prompt: str = None, model: str = None):
    """
    Context manager for GenAI Semantic Conventions.
    Captures prompt, model, and creates a distinct span.
    """
    tracer = get_tracer()
    if tracer is None:
        yield None
        return

    try:
        from opentelemetry import trace as otel_trace
        with tracer.start_as_current_span(name) as span:
            if prompt:
                span.set_attribute("gen_ai.content.prompt", prompt)
            if model:
                span.set_attribute("gen_ai.request.model", model)
            try:
                yield span
            except Exception as e:
                span.record_exception(e)
                span.set_status(otel_trace.Status(otel_trace.StatusCode.ERROR))
                raise
    except Exception:
        yield None


def record_completion(span, completion: str):
    """Helper to add completion to the current span."""
    if span:
        span.set_attribute("gen_ai.content.completion", completion)
