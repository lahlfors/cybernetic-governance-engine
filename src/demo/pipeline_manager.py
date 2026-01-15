import logging
import traceback
from opentelemetry import trace
from google.cloud import aiplatform
from kfp import compiler

from src.demo.state import demo_state
from src.pipelines.green_stack_pipeline import governance_pipeline
from config.settings import Config

logger = logging.getLogger("Demo.PipelineManager")
tracer = trace.get_tracer("src.demo.pipeline")

async def submit_vertex_pipeline(strategy_description: str):
    """
    Submits the Green Stack Pipeline to Vertex AI.
    """
    with tracer.start_as_current_span("GreenStackSubmission") as span:
        trace_id = span.get_span_context().trace_id
        formatted_trace_id = f"{trace_id:032x}"

        logger.info(f"🚀 Submitting Vertex AI Pipeline. Trace ID: {formatted_trace_id}")
        demo_state.pipeline_status = {"status": "submitting", "mode": "vertex", "message": "Compiling Pipeline..."}
        demo_state.latest_trace_id = formatted_trace_id

        try:
            # 1. Compile
            pipeline_file = "green_stack_pipeline.json"
            compiler.Compiler().compile(
                pipeline_func=governance_pipeline,
                package_path=pipeline_file
            )

            # 2. Initialize Vertex AI
            aiplatform.init(
                project=Config.GOOGLE_CLOUD_PROJECT,
                location=Config.GOOGLE_CLOUD_LOCATION,
            )

            # 3. Submit Job
            demo_state.pipeline_status = {"status": "submitting", "mode": "vertex", "message": "Submitting to Vertex AI..."}

            job = aiplatform.PipelineJob(
                display_name="green-stack-governance-demo",
                template_path=pipeline_file,
                parameter_values={
                    "trading_strategy": strategy_description,
                    "target_env": "demo"
                },
                enable_caching=False
            )

            job.submit()

            dashboard_url = job._dashboard_uri()
            logger.info(f"✅ Pipeline Submitted: {dashboard_url}")

            demo_state.pipeline_status = {
                "status": "submitted",
                "mode": "vertex",
                "message": "Pipeline Running on Vertex AI",
                "dashboard_url": dashboard_url
            }

        except Exception as e:
            logger.error(f"❌ Vertex Submission Failed: {e}")
            demo_state.pipeline_status = {"status": "error", "mode": "vertex", "message": f"Vertex Submission Failed: {str(e)}"}
            # Do NOT fallback to local. User requested Vertex ONLY.
            raise e
