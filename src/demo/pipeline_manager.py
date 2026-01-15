import logging
import asyncio
import traceback
import json
import os
from opentelemetry import trace
from google.cloud import aiplatform
from kfp import compiler

from src.demo.state import demo_state
from src.agents.risk_analyst.agent import risk_analyst_agent, ProposedUCA, ConstraintLogic, RiskAssessment
from src.governance.transpiler import transpiler
from src.pipelines.green_stack_pipeline import governance_pipeline
from config.settings import Config

logger = logging.getLogger("Demo.PipelineManager")
tracer = trace.get_tracer("src.demo.pipeline")

async def run_discovery_locally(strategy_description: str):
    """
    Executes the Green Stack Logic LOCALLY.
    Uses real agents and real transpiler. No Mocks.
    """
    with tracer.start_as_current_span("GreenStackDiscoveryLoop_Local") as span:
        trace_id = span.get_span_context().trace_id
        formatted_trace_id = f"{trace_id:032x}"

        logger.info(f"🚀 Starting Local Discovery. Trace ID: {formatted_trace_id}")

        demo_state.pipeline_status = {"status": "running", "mode": "local", "message": "Step 1: Risk Discovery (Analyst AI)..."}
        demo_state.latest_trace_id = formatted_trace_id
        demo_state.latest_generated_rules = ""

        try:
            # Step 1: Risk Discovery (Real Agent Call)
            logger.info("Step 1: Invoking Risk Analyst...")

            agent_input = {
                "provided_trading_strategy": strategy_description,
                "execution_plan_output": {
                    "plan_id": "demo_exec",
                    "steps": [],
                    "risk_factors": []
                },
                "user_risk_attitude": "Aggressive"
            }

            # CALL REAL AGENT - NO FALLBACK
            result = await risk_analyst_agent.invoke(agent_input)
            ucas = result.identified_ucas
            logger.info(f"✅ Agent returned {len(ucas)} UCAs.")

            # Step 2: Transpilation (Real Transpiler)
            demo_state.pipeline_status = {"status": "running", "mode": "local", "message": "Step 2: Policy Transpilation (Code Gen)..."}
            logger.info("Step 2: Transpiling Policies...")

            generated_code = transpiler.transpile_policy(ucas)

            # Step 3: Deployment (Simulated Update of State)
            demo_state.pipeline_status = {"status": "completed", "mode": "local", "message": "✅ Governance Rules Generated."}
            demo_state.latest_generated_rules = generated_code

            logger.info("✅ Local Discovery Complete.")

        except Exception as e:
            logger.error(f"❌ Local Discovery Failed: {e}")
            traceback.print_exc()
            demo_state.pipeline_status = {"status": "error", "mode": "local", "message": f"Pipeline Failed: {str(e)}"}
            raise e

async def submit_vertex_pipeline(strategy_description: str):
    """
    Submits the Green Stack Pipeline to Vertex AI.
    """
    try:
        logger.info("🚀 Submitting Vertex AI Pipeline...")
        demo_state.pipeline_status = {"status": "submitting", "mode": "vertex", "message": "Compiling Pipeline..."}

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

        # Use a default staging bucket if possible, or let Vertex choose
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
        raise e
