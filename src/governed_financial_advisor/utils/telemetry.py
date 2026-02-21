"""
Telemetry configuration for GCP Cloud Logging and Cloud Trace.
Refactored for Centralized Observability (OTLP Collector).
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

class ServiceContextFilter(logging.Filter):
    """Injects serviceContext for GCP Cloud Logging/Error Reporting."""
    def filter(self, record):
        record.serviceContext = {
            "service": os.getenv("SERVICE_NAME", "financial-advisor"),
            "version": os.getenv("DEPLOY_TIMESTAMP", "unknown")
        }
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
    logHandler.addFilter(ServiceContextFilter())
    root_logger.addHandler(logHandler)
    root_logger.setLevel(logging.INFO)

    # Force uvicorn loggers to use our handler
    for log_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        log = logging.getLogger(log_name)
        log.handlers = []
        log.propagate = True

# Initialize logging early
HANDLER_ADDED = False

if os.getenv("ENABLE_LOGGING", "true").lower() == "true":
    setup_canonical_logging()
    logger = logging.getLogger("FinancialAdvisor")
else:
    logger = logging.getLogger("FinancialAdvisor")
    # If logging is disabled or OTEL not configured, ensure we have at least a console handler
    if not HANDLER_ADDED:
        # Default to Console Logging if no other handler is added
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        
        root_logger = logging.getLogger()
        root_logger.addHandler(console_handler)
        # Avoid duplicate handlers if called multiple times
        HANDLER_ADDED = True
        logger.info("⚠️ OTEL disabled. Falling back to standard Console Logging.")

_telemetry_configured = False

def configure_telemetry():
    """
    Configures OpenTelemetry tracing (Centralized Mode).
    Uses standard OTLP exporting to an OpenTelemetry Collector.
    """
    global HANDLER_ADDED
    global _telemetry_configured
    if _telemetry_configured:
        return

    if os.getenv("ENABLE_LOGGING", "true").lower() != "true":
         return

    try:
        if os.getenv("OTEL_TRACES_EXPORTER") == "none":
            logger.info("🚫 OTEL Telemetry explicitly disabled via environment variable.")
            return

        # Import optional dependencies
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter, Compression
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GRPCSpanExporter
        from opentelemetry.sdk.resources import Resource

        # Configure Resource
        resource = Resource.create({
            "service.name": os.getenv("SERVICE_NAME", "financial-advisor"),
            "service.version": os.getenv("DEPLOY_TIMESTAMP", "unknown"),
        })

        # Set up tracer provider
        provider = TracerProvider(resource=resource)
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

        # 2. Centralized Tier / OTel Collector
        otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        
        if otel_endpoint:
            if otel_endpoint.startswith("http://") or otel_endpoint.startswith("https://"):
                # Use HTTP Exporter
                otlp_exporter = OTLPSpanExporter(endpoint=otel_endpoint)
                provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
                logger.info(f"✅ OpenTelemetry: HTTP OTLP Exporter configured at {otel_endpoint}")
            else:
                # Use gRPC Exporter
                otlp_exporter = GRPCSpanExporter(endpoint=otel_endpoint, insecure=True)
                provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
                logger.info(f"✅ OpenTelemetry: gRPC OTLP Exporter configured at {otel_endpoint}")

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
        logger.info("✅ Telemetry configuration complete (Centralized Mode).")

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
    Context manager for GenAI Semantic Conventions (Centralized).
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
    """Helper to record completion metadata."""
    if span and completion:
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

