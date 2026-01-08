import os
import logging
import google.cloud.logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from openinference.instrumentation.langchain import LangChainInstrumentor

def configure_telemetry():
    """
    Configures OpenTelemetry for Google Cloud Trace and Logging,
    instrumented with OpenInference for LangChain/LangGraph.
    """
    # 1. Setup Google Cloud Logging (The Log Explorer)
    # This connects standard Python logging directly to GCP Log Explorer
    try:
        log_client = google.cloud.logging.Client()
        log_client.setup_logging()
    except Exception as e:
        print(f"⚠️ Google Cloud Logging not configured: {e}")

    # Create a standard logger
    logger = logging.getLogger("iso-agent")
    logger.setLevel(logging.INFO)

    # 2. Define the Resource
    resource = Resource(attributes={
        "service.name": "financial-advisor-agent",
        "service.version": "1.0.0",
        "deployment.environment": os.getenv("DEPLOYMENT_ENV", "production")
    })

    # 3. Set up the Provider
    tracer_provider = TracerProvider(resource=resource)
    
    # 4. Configure Exporters
    # Primary: Google Cloud Trace
    try:
        cloud_trace_exporter = CloudTraceSpanExporter()
        tracer_provider.add_span_processor(
            BatchSpanProcessor(cloud_trace_exporter)
        )
    except Exception as e:
        print(f"⚠️ OpenTelemetry Cloud Trace not configured: {e}")
        # Fallback to Console for dev/debug if GCP fails
        # console_exporter = ConsoleSpanExporter()
        # tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))

    # 5. Link Logs to Traces
    # This auto-instruments the logging library to inject trace_id/span_id
    LoggingInstrumentor().instrument(set_logging_format=True)

    # 6. Instrument LangGraph/LangChain (OpenInference)
    # This captures the Agent's internal steps (Nodes, Chains)
    LangChainInstrumentor().instrument(tracer_provider=tracer_provider)

    logger.info("✅ Telemetry configuration complete.")
    return tracer_provider

# Helper to get tracer
def get_tracer():
    return trace.get_tracer(__name__)
