import traceback
import uvicorn
import logging
import asyncio

# Initialize Vertex AI before importing agents
import vertexai
from fastapi import FastAPI, HTTPException
from opentelemetry import trace
from pydantic import BaseModel
import os
from vertexai.preview import reasoning_engines
from google.genai import types

from config.settings import Config
from src.utils.context import user_context
from src.utils.nemo_manager import load_rails, validate_with_nemo
from src.utils.telemetry import configure_telemetry

# Initialize Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Server")

# Initialize Vertex AI
vertexai.init(project=Config.GOOGLE_CLOUD_PROJECT, location=Config.GOOGLE_CLOUD_LOCATION)
logger.info(f"✅ Vertex AI initialized: project={Config.GOOGLE_CLOUD_PROJECT}, location={Config.GOOGLE_CLOUD_LOCATION}")

# Observability
configure_telemetry()

# Initialize App
app = FastAPI(title="Governed Financial Advisor (Gateway)")

# --- GLOBAL SINGLETONS ---
rails = load_rails()

# Reasoning Engine Client
agent_engine_id = os.environ.get("AGENT_ENGINE_ID")
agent_engine = None
if agent_engine_id:
    try:
        agent_engine = reasoning_engines.ReasoningEngine(agent_engine_id)
        logger.info(f"✅ Connected to Agent Engine: {agent_engine_id}")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Agent Engine: {e}")

class QueryRequest(BaseModel):
    prompt: str
    user_id: str = "default_user"
    thread_id: str = "default_thread"

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "financial-advisor-gateway",
        "project_id": Config.GOOGLE_CLOUD_PROJECT,
        "agent_engine_connected": agent_engine is not None
    }

@app.post("/agent/query")
async def query_agent(req: QueryRequest):
    token = user_context.set(req.user_id)
    try:
        # ISO 42001: A.7.2 Accountability - Tag trace with User Identity
        current_span = trace.get_current_span()
        trace_id = None
        if current_span:
            current_span.set_attribute("enduser.id", req.user_id)
            current_span.set_attribute("thread.id", req.thread_id)
            trace_id = f"{current_span.get_span_context().trace_id:032x}"

        # 1. NeMo Security (Gateway Level)
        is_safe, msg = await validate_with_nemo(req.prompt, rails)
        if not is_safe:
            return {"response": msg}

        # 2. Call Reasoning Engine
        if not agent_engine:
             raise HTTPException(status_code=503, detail="Agent Engine not connected")

        # Note: Reasoning Engine query format depends on implementation.
        # ADK agents usually take input via kwargs or specific method if exposed.
        # Assuming standard .query() which ADK maps to.
        # For simplicity, we pass prompt as 'input' or similar if needed.
        # But ReasoningEngine client usually exposes .query()
        try:
            response = agent_engine.query(input=req.prompt)
            # Response structure depends on agent return type.
            # Assuming string or object with 'output'
            full_response = str(response)
        except Exception as run_exc:
             logger.error(f"Agent Engine Execution Failed: {run_exc}")
             raise HTTPException(status_code=500, detail=f"Agent Engine Error: {run_exc}")

        return {
            "response": full_response,
            "trace_id": trace_id
        }

    except Exception as e:
        logger.error(f"❌ Error invoking ADK agent: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        user_context.reset(token)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=Config.PORT)
