# src/governed_financial_advisor/reasoning_engine_service.py

import os
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request
from pydantic import BaseModel
from src.governed_financial_advisor.reasoning_engine import FinancialAdvisorEngine

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ReasoningEngineService")

app = FastAPI(title="Financial Advisor Reasoning Engine")

# Initialize Agent
# We initialize it globally to keep state/connection pooling if applicable
# In a real scalable setup, we might manage lifecycle differently.
PROJECT_ID = os.environ.get("PROJECT_ID")
REGION = os.environ.get("REGION", "us-central1")
REDIS_HOST = os.environ.get("REDIS_HOST") # Passed via env var in container
REDIS_URL = f"redis://{REDIS_HOST}:6379" if REDIS_HOST else None

agent_engine = FinancialAdvisorEngine(
    project=PROJECT_ID,
    location=REGION,
    redis_url=REDIS_URL
)

class QueryRequest(BaseModel):
    query: str
    thread_id: Optional[str] = None

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/query")
async def query_agent(request: QueryRequest):
    """
    Standard endpoint for querying the agent.
    Matches the Reasoning Engine 'query' signature.
    """
    logger.info(f"Received query: {request.query} (Thread: {request.thread_id})")
    try:
        response = agent_engine.query(prompt=request.query, thread_id=request.thread_id)
        return response
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        return {"error": str(e)}

# If Vertex AI Reasoning Engine expects specific routes, we can add them.
# Usually custom container implies we define the contract.
