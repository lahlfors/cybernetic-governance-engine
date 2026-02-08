import logging
import uvicorn
import traceback
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from config.settings import Config
from src.governed_financial_advisor.orchestrator import FinancialAdvisorOrchestrator
from src.governed_financial_advisor.utils.nemo_manager import load_rails, validate_with_nemo
from src.governed_financial_advisor.utils.telemetry import configure_telemetry
from src.governed_financial_advisor.infrastructure.gateway_client import gateway_client
from src.governed_financial_advisor.utils.context import user_context

# Configure Telemetry
configure_telemetry()

logger = logging.getLogger("Server")

# Global Orchestrator
orchestrator = FinancialAdvisorOrchestrator()
rails = load_rails()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Governed Financial Advisor (Orchestrator Mode)...")
    yield
    logger.info("🛑 Shutting down...")
    await gateway_client.close()

app = FastAPI(title="Governed Financial Advisor", lifespan=lifespan)
FastAPIInstrumentor.instrument_app(app)

class QueryRequest(BaseModel):
    prompt: str
    user_id: str = "default_user"
    thread_id: str = "default_thread"

@app.get("/health")
def health_check():
    return {"status": "ok", "mode": "orchestrator"}

@app.post("/agent/query")
async def query_agent(req: QueryRequest):
    token = user_context.set(req.user_id)
    try:
        # 1. NeMo Guardrails (Input)
        is_safe, msg = await validate_with_nemo(req.prompt, rails)
        if not is_safe:
            return {"response": msg}

        # 2. Orchestrator Execution
        # Run synchronous orchestrator in thread pool if needed, or if it has async run method use it.
        # Check orchestrator source: it has 'run' (sync) that calls nodes.
        # Some nodes are async (evaluator_node). Orchestrator 'run' calls 'asyncio.run' internally?
        # Yes, based on the snippet I read earlier.

        # We can run the sync 'run' method directly.
        state = orchestrator.run(req.prompt, req.user_id, req.thread_id)

        # 3. Extract Response
        msgs = state.get("messages", [])
        response_text = "No response generated."
        if msgs:
            last_msg = msgs[-1]
            if hasattr(last_msg, "content"):
                response_text = last_msg.content
            elif isinstance(last_msg, dict):
                response_text = last_msg.get("content", "")
            elif isinstance(last_msg, tuple):
                response_text = last_msg[1]
            else:
                response_text = str(last_msg)

        return {"response": response_text}

    except Exception as e:
        logger.error(f"Error processing query: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        user_context.reset(token)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=Config.PORT)