"""
Telemetry configuration for GCP Cloud Logging and Cloud Trace.
"""
import logging
import os
import contextlib
import random
from typing import Any, Dict

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
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
        
        # Try to configure Google Cloud Trace
        try:
            from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
            from src.infrastructure.telemetry.processors.genai_cost_optimizer import GenAICostOptimizerProcessor
            from src.infrastructure.telemetry.exporters.parquet_exporter import ParquetSpanExporter
            
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
