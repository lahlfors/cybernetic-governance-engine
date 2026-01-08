import os
import sys
import uvicorn
import traceback
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Imports
from google.genai.types import Part, UserContent 
from opentelemetry import trace
from opentelemetry.instrumentation.langchain import LangchainInstrumentor

# Project Imports
from financial_advisor.telemetry import configure_telemetry
from financial_advisor.nemo_manager import create_nemo_manager, validate_with_nemo
from financial_advisor.graph import create_graph

app = FastAPI(title="Governed Financial Advisor")

# Setup OTel
configure_telemetry()
LangchainInstrumentor().instrument() # Auto-traces Graph & ADK Wrapper

# Initialize Graph
graph = create_graph(redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379"))

# Guardrails
try:
    rails = create_nemo_manager()
    rails_active = True
    print("✅ NeMo Guardrails initialized.")
except Exception as e:
    print(f"⚠️ NeMo Guardrails failed to initialize: {e}")
    rails = None
    rails_active = False

class AgentQuery(BaseModel):
    input: str
    thread_id: str = "default_thread"

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "financial-advisor-agent"}

@app.post("/agent/query")
async def query_endpoint(req: AgentQuery):
    # 1. NeMo Security Check
    if rails_active:
        safe, msg = await validate_with_nemo(req.input, rails)
        if not safe:
            return {"response": msg} # Blocked

    # 2. Graph Execution (Supervisor -> ADK Worker)
    try:
        res = await graph.ainvoke(
            {"messages": [("user", req.input)]},
            config={"configurable": {"thread_id": req.thread_id}}
        )
        # Extract last AI message
        last_msg = res["messages"][-1]
        content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        
        return {"response": content}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
