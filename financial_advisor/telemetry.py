import logging
import os
import contextlib
from opentelemetry import trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from google.auth.exceptions import DefaultCredentialsError

logger = logging.getLogger("Telemetry")
tracer = trace.get_tracer("financial_advisor.genai")

def setup_telemetry(app):
    """
    Configures OpenTelemetry for the application.
    - Sets up the TracerProvider.
    - Configures CloudTraceSpanExporter (for GCP) or ConsoleSpanExporter (fallback).
    - Instruments FastAPI and Requests.
    """
    # 1. Configure Tracer Provider
    trace.set_tracer_provider(TracerProvider())
    tracer_provider = trace.get_tracer_provider()

    # 2. Configure Exporter
    try:
        # Try to use Google Cloud Trace Exporter
        # This requires GOOGLE_APPLICATION_CREDENTIALS or running in GCP
        cloud_exporter = CloudTraceSpanExporter()
        span_processor = BatchSpanProcessor(cloud_exporter)
        tracer_provider.add_span_processor(span_processor)
        logger.info("✅ OpenTelemetry: Google Cloud Trace Exporter configured.")
    except DefaultCredentialsError:
        # Fallback for local dev without creds
        logger.warning("⚠️ OpenTelemetry: GCP Credentials not found. Falling back to Console Exporter.")
        console_exporter = ConsoleSpanExporter()
        span_processor = BatchSpanProcessor(console_exporter)
        tracer_provider.add_span_processor(span_processor)
    except Exception as e:
        logger.error(f"❌ OpenTelemetry: Failed to configure exporter: {e}")

    # 3. Instrument Requests (Outgoing HTTP calls like OPA)
    RequestsInstrumentor().instrument()
    logger.info("✅ OpenTelemetry: Requests instrumented.")

    # 4. Instrument FastAPI (Incoming HTTP requests)
    if app:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("✅ OpenTelemetry: FastAPI instrumented.")

@contextlib.contextmanager
def genai_span(name: str, prompt: str = None, model: str = None):
    """
    Context manager for GenAI Semantic Conventions (v1.37+ draft).
    Captures prompt, model, and creates a distinct span.
    """
    with tracer.start_as_current_span(name) as span:
        if prompt:
            span.set_attribute("gen_ai.content.prompt", prompt)
        if model:
            span.set_attribute("gen_ai.request.model", model)

        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR))
            raise

def record_completion(span, completion: str):
    """Helper to add completion to the current span."""
    if span:
        span.set_attribute("gen_ai.content.completion", completion)
