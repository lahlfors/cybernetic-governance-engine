import os
import sys
import uvicorn
import traceback
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from opentelemetry import trace
from opentelemetry.instrumentation.langchain import LangchainInstrumentor

# Initialize Vertex AI before importing agents
import vertexai
from config.settings import Config

vertexai.init(project=Config.GOOGLE_CLOUD_PROJECT, location=Config.GOOGLE_CLOUD_LOCATION)
print(f"✅ Vertex AI initialized: project={Config.GOOGLE_CLOUD_PROJECT}, location={Config.GOOGLE_CLOUD_LOCATION}")

from src.utils.nemo_manager import load_rails, validate_with_nemo
from src.graph.graph import create_graph
from src.utils.context import user_context
from src.utils.telemetry import configure_telemetry

# Observability
configure_telemetry()
LangchainInstrumentor().instrument() # Traces Graph nodes (including Agent calls)

app = FastAPI(title="Governed Financial Advisor (Graph Orchestrated)")

# --- GLOBAL SINGLETONS ---
rails = load_rails()
# Use localhost as default Redis URL if not set
graph = create_graph(redis_url=Config.REDIS_URL)

class QueryRequest(BaseModel):
    prompt: str
    user_id: str = "default_user" 
    thread_id: str = "default_thread"

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "financial-advisor-graph-agent"}

@app.post("/agent/query")
async def query_agent(req: QueryRequest):
    token = user_context.set(req.user_id)
    try:
        # ISO 42001: A.7.2 Accountability - Tag trace with User Identity
        current_span = trace.get_current_span()
        if current_span:
            current_span.set_attribute("enduser.id", req.user_id)
            current_span.set_attribute("thread.id", req.thread_id)

        # 1. NeMo Security
        is_safe, msg = await validate_with_nemo(req.prompt, rails)
        if not is_safe:
            return {"response": msg}

        # 2. Graph Execution (Calls Existing Agents)
        # Using ainvoke to run the graph asynchronously
        res = await graph.ainvoke(
            {"messages": [("user", req.prompt)]},
            config={"recursion_limit": 20, "configurable": {"thread_id": req.thread_id}}
        )
        
        # Extract the last message content
        return {"response": res["messages"][-1].content}

    except Exception as e:
        print(f"❌ Error invoking agent graph: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        user_context.reset(token)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=Config.PORT)
