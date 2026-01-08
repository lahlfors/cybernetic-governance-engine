import os
import sys
import uvicorn
import traceback
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Imports
from google.adk.runners import InMemoryRunner
from google.genai.types import Part, UserContent 

# Project Imports
from financial_advisor.agent import financial_coordinator
from financial_advisor.telemetry import configure_telemetry
from financial_advisor.nemo_manager import create_nemo_manager
from financial_advisor.context import user_context
# --- NEW: Infrastructure Import ---
from financial_advisor.infrastructure.vertex_memory import create_memory_service

app = FastAPI(title="Governed Financial Advisor")

configure_telemetry()

# --- GLOBAL SINGLETONS ---
runner = InMemoryRunner(agent=financial_coordinator)

import datetime
# Force update timestamp
print(f"DEBUG: Server started (Fixed Session) at {datetime.datetime.now()}", file=sys.stderr, flush=True)

# Guardrails
try:
    rails = create_nemo_manager()
    rails_active = True
    print("✅ NeMo Guardrails initialized.")
except Exception as e:
    print(f"⚠️ NeMo Guardrails failed to initialize: {e}")
    rails = None
    rails_active = False

# --- NEW: Memory Initialization ---
# This sets up the singleton for the Agent to use later
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
AGENT_ENGINE_ID = os.environ.get("AGENT_ENGINE_ID")

if AGENT_ENGINE_ID:
    try:
        create_memory_service(PROJECT_ID, LOCATION, AGENT_ENGINE_ID)
        print(f"✅ Native ADK Memory Service Active (Engine: {AGENT_ENGINE_ID})")
    except Exception as e:
        print(f"❌ Failed to init Memory Service: {e}")
else:
    print("⚠️ AGENT_ENGINE_ID not set. Memory will be ephemeral.")

class QueryRequest(BaseModel):
    prompt: str
    user_id: str = "default_user" 

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "financial-advisor-agent"}

@app.post("/agent/query")
async def query_agent(request: QueryRequest):
    token = user_context.set(request.user_id)
    try:
        # --- Layer 1: Context Retrieval (REMOVED) ---
        # Handled automatically by PreloadMemoryTool in agent.py
        
        # --- Layer 2: Input Guardrails ---
        if rails_active:
            try:
                # Basic check 
                pass 
            except Exception as e:
                print(f"Guardrails Input Check Warning: {e}")

        # --- Layer 3: Execution ---
        # --- Layer 3: Execution ---
        # Let the runner manage session creation implicitly (to avoid InMemoryRunner lookup issues)
        
        # Pass raw prompt. Tool will augment context.
        content = UserContent(parts=[Part(text=request.prompt)])
        
        final_text = ""
        async for event in runner.run_async(
            session_id=None,
            user_id=request.user_id,
            new_message=content
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        final_text += part.text
        
        # --- Layer 4: Output Guardrails ---
        if rails_active:
            try:
                # Output verification logic 
                pass
            except Exception as e:
                print(f"Guardrails Output Check Warning: {e}")

        # --- Layer 5: Context Storage (REMOVED) ---
        # Handled automatically by save_memory_callback in agent.py
        
        return {"response": final_text}

    except Exception as e:
        print(f"❌ Error invoking agent: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        user_context.reset(token)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
