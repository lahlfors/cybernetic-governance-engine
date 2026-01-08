import os
import sys
import uvicorn
import traceback
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from financial_advisor.telemetry import configure_telemetry
from financial_advisor.nemo_manager import create_nemo_manager

# New Imports
from financial_advisor.graph import app as graph_app

app = FastAPI(title="Governed Financial Advisor")

configure_telemetry()

# Guardrails
try:
    rails = create_nemo_manager()
    rails_active = True
    print("✅ NeMo Guardrails initialized.")
except Exception as e:
    print(f"⚠️ NeMo Guardrails failed to initialize: {e}")
    rails = None
    rails_active = False

class QueryRequest(BaseModel):
    message: str
    user_id: str = "default_user"

# Endpoint for NeMo compliant chat
class ChatCompletionRequest(BaseModel):
    text: str

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "financial-advisor-agent-langgraph"}

# --- NE MO GUARDRAILS ENDPOINT (Secure) ---
@app.post("/v1/chat/completions")
async def chat_endpoint(request: ChatCompletionRequest):
    if not rails or not rails_active:
        raise HTTPException(status_code=503, detail="NeMo Guardrails not initialized")

    try:
        # SECURE: Wraps the flow in Input -> LLM -> Output rails
        response = await rails.generate_async(
            messages=[{"role": "user", "content": request.text}]
        )
        content = response.content if hasattr(response, 'content') else str(response)
        return {"content": content}

    except Exception as e:
        print(f"Policy Violation: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Policy Violation: {str(e)}")

# --- DIRECT GRAPH ENDPOINT (Secured via Input Check) ---
@app.post("/agent/query")
async def query_agent(request: QueryRequest):
    try:
        # --- SECURE: Input Guardrail Check ---
        if rails_active and rails:
            try:
                # We use NeMo to validate the input prompt.
                await rails.generate_async(messages=[{"role": "user", "content": request.message}])
            except Exception as e:
                print(f"Guardrails Input Check Warning/Block: {e}")
                raise HTTPException(status_code=400, detail=f"Input Policy Violation: {str(e)}")

        config = {"configurable": {"thread_id": request.user_id}}
        
        final_state = await graph_app.ainvoke(
            {
                "messages": [("user", request.message)],
                "user_id": request.user_id
            },
            config=config
        )
        
        bot_response = final_state["messages"][-1].content
        return {"response": bot_response}

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error invoking agent: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
