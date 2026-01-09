import os
import sys
import uvicorn
import traceback
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from opentelemetry import trace
from opentelemetry.instrumentation.langchain import LangchainInstrumentor

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
redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
graph = create_graph(redis_url=redis_url)

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
        # 1. NeMo Security
        is_safe, msg = await validate_with_nemo(req.prompt, rails)
        if not is_safe:
            return {"response": msg}

        # 2. Graph Execution (Calls Existing Agents)
        # Using ainvoke to run the graph asynchronously
        res = await graph.ainvoke(
            {"messages": [("user", req.prompt)]},
            config={"configurable": {"thread_id": req.thread_id}}
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
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
