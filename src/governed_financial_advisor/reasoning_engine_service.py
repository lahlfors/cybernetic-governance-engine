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
PROJECT_ID = os.environ.get("PROJECT_ID")
REGION = os.environ.get("REGION", "us-central1")

agent_engine = FinancialAdvisorEngine(
    project=PROJECT_ID,
    location=REGION
)

# Trigger setup explicitly if running in this standalone service mode
# Reasoning Engine Runtime might call this automatically, but here we control the lifecycle
agent_engine.set_up()

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
