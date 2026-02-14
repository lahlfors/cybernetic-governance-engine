"""
Telemetry configuration for GCP Cloud Logging and Cloud Trace.
Refactored for Hybrid Observability (LangSmith Async + AgentSight).
"""
import contextlib
import logging
import os
import sys
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

def configure_telemetry():
    """
    Configures OpenTelemetry tracing (Hybrid Mode).
    Uses standard async BatchSpanProcessors to capture payloads for LangSmith,
    while AgentSight handles system-level correlation via HTTP headers.
    """
    global _telemetry_configured
    if _telemetry_configured:
        return

    try:
        # Import optional dependencies
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter, Compression

        # Set up tracer provider
        provider = TracerProvider()
        trace.set_tracer_provider(provider)

        # 1. Hot Tier: Cloud Trace (or OTLP fallback)
        try:
            from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
            gcp_project = os.environ.get("GOOGLE_CLOUD_PROJECT")
            if gcp_project:
                cloud_exporter = CloudTraceSpanExporter(project_id=gcp_project)
                provider.add_span_processor(BatchSpanProcessor(cloud_exporter))
                logger.info(f"✅ OpenTelemetry: Cloud Trace configured for project {gcp_project}")
        except Exception:
            pass

        # 2. Cold Tier / LangSmith (Standard Async Tracing)
        otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if otel_endpoint:
             otel_headers = {}
             if os.getenv("OTEL_EXPORTER_OTLP_HEADERS"):
                  pairs = os.getenv("OTEL_EXPORTER_OTLP_HEADERS").split(",")
                  for pair in pairs:
                       k, v = pair.split("=", 1)
                       otel_headers[k] = v

             otlp_exporter = OTLPSpanExporter(endpoint=otel_endpoint, headers=otel_headers)
             provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
             logger.info(f"✅ OpenTelemetry: OTLP Exporter configured at {otel_endpoint}")

        # LangSmith Integration (Via OTLP)
        langsmith_key = os.getenv("LANGSMITH_API_KEY")
        langsmith_endpoint = os.environ.get("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

        if langsmith_key:
            try:
                langsmith_otlp_endpoint = f"{langsmith_endpoint.rstrip('/')}/otel/v1/traces"
                
                langsmith_exporter = OTLPSpanExporter(
                    endpoint=langsmith_otlp_endpoint,
                    headers={"x-api-key": langsmith_key.strip()},
                    compression=Compression.NoCompression
                )
                provider.add_span_processor(BatchSpanProcessor(langsmith_exporter))
                logger.info(f"✅ LangSmith: Async Tracing configured at {langsmith_otlp_endpoint}")
            except Exception as e:
                logger.warning(f"⚠️ LangSmith configuration failed: {e}")

        # Instrument HTTP libraries
        try:
            from opentelemetry.instrumentation.requests import RequestsInstrumentor
            RequestsInstrumentor().instrument()
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
            HTTPXClientInstrumentor().instrument()
            logger.info("✅ OpenTelemetry: HTTP instrumentation enabled.")
        except ImportError:
            pass

        _telemetry_configured = True
        logger.info("✅ Telemetry configuration complete (Hybrid Mode).")

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
    Context manager for GenAI Semantic Conventions (Hybrid).
    Captures prompt content for LangSmith (async), while AgentSight captures raw traffic.
    """
    tracer = get_tracer()
    if tracer is None:
        yield None
        return

    try:
        from opentelemetry import trace as otel_trace
        with tracer.start_as_current_span(name) as span:
            # HYBRID: We restore payload capture here for LangSmith utility.
            # The 'BatchSpanProcessor' ensures this is handled asynchronously.
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
    """Helper to record completion metadata (Hybrid)."""
    if span and completion:
        # HYBRID: We restore payload capture here for LangSmith utility.
        span.set_attribute("gen_ai.content.completion", completion)

def record_usage(span, usage):
    """
    Helper to add token usage stats to the current span.
    """
    if not span or not usage:
        return

    prompt_tokens = None
    completion_tokens = None
    total_tokens = None

    if hasattr(usage, "prompt_tokens"):
        prompt_tokens = getattr(usage, "prompt_tokens", 0)
        completion_tokens = getattr(usage, "completion_tokens", 0)
        total_tokens = getattr(usage, "total_tokens", 0)
    elif isinstance(usage, dict):
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        total_tokens = usage.get("total_tokens")

    if prompt_tokens is not None:
        span.set_attribute("gen_ai.usage.input_tokens", prompt_tokens)
    if completion_tokens is not None:
        span.set_attribute("gen_ai.usage.output_tokens", completion_tokens)
    if total_tokens is not None:
        span.set_attribute("gen_ai.usage.total_tokens", total_tokens)
