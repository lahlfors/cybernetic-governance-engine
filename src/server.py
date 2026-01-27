import traceback
import uvicorn
import logging
import asyncio

# Initialize Vertex AI before importing agents
import vertexai
from fastapi import FastAPI, HTTPException
from opentelemetry import trace
from pydantic import BaseModel
from google.adk.runners import Runner
from google.adk.sessions import Session, InMemorySessionService
from google.genai import types

from config.settings import Config
from src.agents.financial_advisor.agent import root_agent
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
app = FastAPI(title="Governed Financial Advisor (ADK Native)")

# --- GLOBAL SINGLETONS ---
rails = load_rails()

# Initialize Session Service (InMemory for Local/Container, Native VertexAi in Prod)
session_service = InMemorySessionService()

class QueryRequest(BaseModel):
    prompt: str
    user_id: str = "default_user"
    thread_id: str = "default_thread"

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "financial-advisor-adk-native",
        "project_id": Config.GOOGLE_CLOUD_PROJECT
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

        # 1. NeMo Security
        is_safe, msg = await validate_with_nemo(req.prompt, rails)
        if not is_safe:
            return {"response": msg}

        # 2. ADK Native Execution
        # Ensure session exists
        session = await session_service.get_session(
            app_name="financial_advisor",
            user_id=req.user_id,
            session_id=req.thread_id
        )
        if not session:
            new_session = Session(
                app_name="financial_advisor",
                user_id=req.user_id,
                session_id=req.thread_id
            )
            # Correct API usage: create_session(session)
            await session_service.create_session(new_session)
            session = new_session

        # Create ADK Runner
        runner = Runner(
            agent=root_agent,
            session_service=session_service,
            app_name="financial_advisor"
        )

        # Prepare input
        new_message = types.Content(
            role="user",
            parts=[types.Part(text=req.prompt)]
        )

        # Execute Runner Loop
        # The runner handles routing via tools (transfer_to_agent) automatically
        answer_parts = []
        # Run asynchronously
        try:
             # Runner.run is a generator. We iterate to process events.
             # Note: Runner operations might block if not fully async,
             # but ADK 0.14+ supports async via event loop.
             for event in runner.run(
                 user_id=req.user_id,
                 session_id=req.thread_id,
                 new_message=new_message
             ):
                if hasattr(event, 'content') and event.content:
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            answer_parts.append(part.text)
        except Exception as run_exc:
             logger.error(f"ADK Execution Failed: {run_exc}")
             raise HTTPException(status_code=500, detail=f"Agent Execution Error: {run_exc}")

        full_response = "".join(answer_parts)

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
