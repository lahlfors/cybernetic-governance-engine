from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from src.governed_financial_advisor.demo.pipeline_manager import submit_vertex_pipeline
from src.governed_financial_advisor.demo.state import demo_state

demo_router = APIRouter(prefix="/demo", tags=["demo"])

class PipelineRequest(BaseModel):
    strategy: str

class ContextRequest(BaseModel):
    latency: float
    risk_profile: str = "Balanced"

@demo_router.post("/pipeline")
async def start_pipeline(req: PipelineRequest, background_tasks: BackgroundTasks):
    """Starts the governance pipeline (Vertex AI Only) in the background."""
    background_tasks.add_task(submit_vertex_pipeline, req.strategy)
    return {"status": "started", "mode": "vertex", "message": "Submitting to Vertex AI..."}

@demo_router.get("/status")
def get_status():
    """Returns the current demo state."""
    return {
        "pipeline": demo_state.pipeline_status,
        "latency": demo_state.simulated_latency,
        "rules": demo_state.latest_generated_rules,
        "trace_id": demo_state.latest_trace_id
    }

@demo_router.post("/context")
def set_context(req: ContextRequest):
    """Updates the simulated environment context."""
    demo_state.simulated_latency = req.latency
    demo_state.forced_risk_profile = req.risk_profile
    return {"status": "updated", "latency": req.latency}

@demo_router.post("/reset")
def reset_demo():
    """Resets the demo state."""
    demo_state.reset()
    return {"status": "reset"}
