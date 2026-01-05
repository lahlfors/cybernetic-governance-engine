"""
Telemetry configuration for GCP Cloud Logging and Cloud Trace.
"""
import logging
import os
import contextlib

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("FinancialAdvisor")

_telemetry_configured = False

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
        
        # Try to configure Google Cloud Trace
        try:
            from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
            
            # Set up tracer provider
            provider = TracerProvider()
            trace.set_tracer_provider(provider)
            
            # Configure Cloud Trace exporter
            cloud_exporter = CloudTraceSpanExporter()
            span_processor = BatchSpanProcessor(cloud_exporter)
            provider.add_span_processor(span_processor)
            logger.info("✅ OpenTelemetry: Google Cloud Trace Exporter configured.")
            
            # Instrument the requests library for HTTP tracing
            try:
                from opentelemetry.instrumentation.requests import RequestsInstrumentor
                RequestsInstrumentor().instrument()
                logger.info("✅ OpenTelemetry: Requests HTTP library instrumented.")
            except ImportError:
                logger.warning("⚠️ Requests instrumentation not available (install opentelemetry-instrumentation-requests)")
            except Exception as e:
                logger.warning(f"⚠️ Requests instrumentation failed: {e}")
                
        except Exception as e:
            logger.warning(f"⚠️ OpenTelemetry Cloud Trace not configured: {e}")
        
        # Try to configure Google Cloud Logging
        try:
            import google.cloud.logging
            
            client = google.cloud.logging.Client()
            client.setup_logging()
            logger.info("✅ Google Cloud Logging configured.")
        except Exception as e:
            logger.warning(f"⚠️ Google Cloud Logging not configured: {e}")
        
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
        return trace.get_tracer("financial_advisor.genai")
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

