import traceback

import uvicorn

# Initialize Vertex AI before importing agents
# import vertexai
# vertexai.init(project=Config.GOOGLE_CLOUD_PROJECT, location=Config.GOOGLE_CLOUD_LOCATION)
# print(f"✅ Vertex AI initialized: project={Config.GOOGLE_CLOUD_PROJECT}, location={Config.GOOGLE_CLOUD_LOCATION}")

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.langchain import LangchainInstrumentor
from pydantic import BaseModel

from config.settings import Config
from src.governed_financial_advisor.demo.router import demo_router
from src.governed_financial_advisor.graph.graph import create_graph
from src.governed_financial_advisor.utils.context import user_context
from src.governed_financial_advisor.utils.nemo_manager import load_rails, validate_with_nemo
from src.governed_financial_advisor.utils.telemetry import configure_telemetry
from src.governed_financial_advisor.infrastructure.gateway_client import gateway_client

# Observability
configure_telemetry()
LangchainInstrumentor().instrument() # Traces Graph nodes (including Agent calls)

# --- LIFESPAN (Startup/Shutdown) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Graph (and Redis)
    print("🔄 Initializing Agent Graph...")
    app.state.graph = create_graph(redis_url=Config.REDIS_URL)
    
    # Initialize Redis Indices if using Redis Checkpointer (langgraph-checkpoint-redis)
    try:
        if hasattr(app.state.graph, "checkpointer") and app.state.graph.checkpointer:
            cp = app.state.graph.checkpointer
            # Check for AsyncRedisSaver (lazy check to avoid import)
            if "RedisSaver" in str(type(cp)):
                print("Checking Redis Checkpointer setup...")
                if hasattr(cp, "setup"):
                    print("⚙️ Running Redis Checkpointer setup()...")
                    await cp.setup()
                    print("✅ Redis Checkpointer setup complete")
    except Exception as e:
        print(f"⚠️ Failed to setup Redis Checkpointer: {e}")

    print("✅ Agent Graph Initialized")
    yield
    # Shutdown
    print("🛑 Shutting down...")
    await gateway_client.close()

app = FastAPI(title="Governed Financial Advisor (Graph Orchestrated)", lifespan=lifespan)
FastAPIInstrumentor.instrument_app(app) # Enable automatic request tracing
app.include_router(demo_router)

# --- GLOBAL SINGLETONS ---
rails = load_rails()
# Graph is now in app.state.graph

class QueryRequest(BaseModel):
    prompt: str
    user_id: str = "default_user"
    thread_id: str = "default_thread"

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "financial-advisor-graph-agent",
        "project_id": Config.GOOGLE_CLOUD_PROJECT
    }

@app.post("/agent/query")
async def query_agent(req: QueryRequest, request: Request):
    token = user_context.set(req.user_id)
    try:
        # ISO 42001: A.7.2 Accountability - Tag trace with User Identity
        current_span = trace.get_current_span()
        trace_id = None
        if current_span:
            current_span.set_attribute("enduser.id", req.user_id)
            current_span.set_attribute("thread.id", req.thread_id)
            # Capture trace_id for UI ONLY if sampled
            ctx = current_span.get_span_context()
            if ctx.trace_flags.sampled:
                trace_id = f"{ctx.trace_id:032x}"

        # 1. NeMo Security
        is_safe, msg = await validate_with_nemo(req.prompt, rails)
        print(f"DEBUG: NeMo is_safe={is_safe}, msg='{msg}'")

        if not is_safe:
            return {"response": msg, "trace_id": trace_id}
        
        # If NeMo generated a valid response (e.g. greeting), return it
        if msg:
            print("DEBUG: NeMo handled response.")
            return {"response": msg, "trace_id": trace_id}

        # 2. Graph Execution (Calls Existing Agents)
        print(f"DEBUG: Invoking Graph with prompt '{req.prompt}'")
        res = await request.app.state.graph.ainvoke(
            {"messages": [("user", req.prompt)], "user_id": req.user_id},
            {"recursion_limit": 20, "configurable": {"thread_id": req.thread_id}}
        )
        print(f"DEBUG: Graph result messages keys: {res.keys() if res else 'None'}")
        if res and "messages" in res and res["messages"]:
             print(f"DEBUG: Last message content: '{res['messages'][-1].content}'")

        # Extract the last message content
        return {
            "response": res["messages"][-1].content,
            "trace_id": trace_id
        }

    except Exception as e:
        print(f"❌ Error invoking agent graph: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        user_context.reset(token)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=Config.PORT)
