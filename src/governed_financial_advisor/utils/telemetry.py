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

    # C. READ: Default (Chat) -> Variable Sampling (Default 1%)
    # We assume if it's not Write/Risky, it's Read/Chat
    sampling_rate = float(os.getenv("TRACE_SAMPLING_RATE", "0.01"))
    if random.random() < sampling_rate:
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
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        # Try to configure Google Cloud Trace
        try:
            # Set up tracer provider
            provider = TracerProvider()
            trace.set_tracer_provider(provider)

            # 1. Define Exporters
            # Hot Tier: Cloud Trace
            try:
                from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
                gcp_project = os.environ.get("GOOGLE_CLOUD_PROJECT")
                cloud_exporter = CloudTraceSpanExporter(project_id=gcp_project)
                hot_processor = BatchSpanProcessor(cloud_exporter)

                # Optimizer Processor (Correct Import)
                try:
                    from src.governed_financial_advisor.infrastructure.telemetry.processors.genai_cost_optimizer import (
                        GenAICostOptimizerProcessor,
                    )
                except ImportError as e:
                    logger.warning(f"⚠️ Optimizer Processor import failed: {e}")
                    raise

                # Cold Tier: OTLP (Standard/Arrow-compatible)
                # Only enable if explicitly configured to avoid localhost connection errors in GKE
                otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
                cold_processor = None

                if otel_endpoint:
                    otel_headers = {}
                    if os.getenv("OTEL_EXPORTER_OTLP_HEADERS"):
                         pairs = os.getenv("OTEL_EXPORTER_OTLP_HEADERS").split(",")
                         for pair in pairs:
                              k, v = pair.split("=", 1)
                              otel_headers[k] = v

                    otlp_exporter = OTLPSpanExporter(endpoint=otel_endpoint, headers=otel_headers)
                    cold_processor = BatchSpanProcessor(otlp_exporter)
                    logger.info(f"✅ OpenTelemetry: OTLP Exporter configured at {otel_endpoint}")
                
                # LangSmith Integration (Automatic if Env Vars present)
                langsmith_key = os.getenv("LANGSMITH_API_KEY")
                langsmith_endpoint = os.environ.get("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

                if langsmith_key:
                    try:
                        # 1. Configure Tracing (OTLP to LangSmith)
                        # LangSmith OTLP endpoint: /otel/v1/traces
                        langsmith_otlp_endpoint = f"{langsmith_endpoint.rstrip('/')}/otel/v1/traces"

                        # Set Env Vars for OTLP (Standard way)
                        # LangSmith uses "x-api-key" header
                        os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = langsmith_otlp_endpoint
                        os.environ["OTEL_EXPORTER_OTLP_TRACES_HEADERS"] = f"x-api-key={langsmith_key.strip()}"

                        from opentelemetry.exporter.otlp.proto.http.trace_exporter import Compression

                        # Use default constructor which reads env vars
                        langsmith_exporter = OTLPSpanExporter(
                            compression=Compression.NoCompression
                        )
                        # Add as a separate processor
                        provider.add_span_processor(BatchSpanProcessor(langsmith_exporter))
                        logger.info(f"✅ LangSmith: Tracing configured at {langsmith_otlp_endpoint}")

                    except Exception as e:
                        logger.warning(f"⚠️ LangSmith configuration failed: {e}")
                else:
                    logger.info("ℹ️ LangSmith: Credentials not found, skipping integration.")
                
                if not cold_processor:
                    logger.info("ℹ️ OpenTelemetry: OTEL_EXPORTER_OTLP_ENDPOINT not set. Using NoOp Cold Tier.")
                    # Define lightweight NoOp processor to satisfy optimizer contract
                    class NoOpSpanProcessor:
                        def on_start(self, span, parent_context=None): pass
                        def on_end(self, span): pass
                        def shutdown(self): pass
                        def force_flush(self, timeout_millis=30000): return True
                    cold_processor = NoOpSpanProcessor()



                # 2. Configure Optimizer Processor
                # Routes Sampled/Audit (Cold) -> OTLP (Full Fidelity)
                # Routes All (Hot) -> Cloud Trace (Stripped)
                optimizer = GenAICostOptimizerProcessor(
                    hot_processor=hot_processor,
                    cold_processor=cold_processor,
                    pricing_rule=smart_sampling
                )
                provider.add_span_processor(optimizer)
                logger.info("✅ OpenTelemetry: Tiered Observability (Cost Optimizer) configured with OTLP Cold Tier.")

            except Exception as e:
                logger.warning(f"⚠️ Telemetry Pipeline Logic failed: {e}")
                # Fallback: Just add Cloud Trace if optimizer failed
                try:
                     from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
                     gcp_project = os.environ.get("GOOGLE_CLOUD_PROJECT")
                     cloud_exporter = CloudTraceSpanExporter(project_id=gcp_project)
                     provider.add_span_processor(BatchSpanProcessor(cloud_exporter))
                     logger.info("✅ OpenTelemetry: Fallback to simple Cloud Trace.")
                except Exception:
                     pass

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

def record_usage(span, usage):
    """
    Helper to add token usage stats to the current span.
    Handles both Pydantic objects (OpenAI) and dictionaries.
    Terms mapped to GenAI Semantic Conventions:
    - prompt_tokens -> gen_ai.usage.input_tokens
    - completion_tokens -> gen_ai.usage.output_tokens
    - total_tokens -> gen_ai.usage.total_tokens
    """
    if not span or not usage:
        return

    prompt_tokens = None
    completion_tokens = None
    total_tokens = None

    # Handle Pydantic model (OpenAI) or dict
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
        # Also set prompt_tokens for broader compatibility if needed
        span.set_attribute("gen_ai.usage.prompt_tokens", prompt_tokens)
        
    if completion_tokens is not None:
        span.set_attribute("gen_ai.usage.output_tokens", completion_tokens)
        span.set_attribute("gen_ai.usage.completion_tokens", completion_tokens)
        
    if total_tokens is not None:
        span.set_attribute("gen_ai.usage.total_tokens", total_tokens)
