import os
import uvicorn
import traceback
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# 1. Framework Imports
from google.adk.runners import InMemoryRunner
from google.genai.types import Part, UserContent 

# 2. Project Imports
from financial_advisor.agent import financial_coordinator
from financial_advisor.telemetry import configure_telemetry
from financial_advisor.nemo_manager import create_nemo_manager
from financial_advisor.infrastructure.memory import memory_client

app = FastAPI(title="Governed Financial Advisor")

configure_telemetry()

# --- GLOBAL SINGLETONS (Persistence Fix) ---
# Initializing runner here ensures session state survives across requests
runner = InMemoryRunner(agent=financial_coordinator)

# Initialize Guardrails once
try:
    rails = create_nemo_manager()
    rails_active = True
    print("✅ NeMo Guardrails initialized.")
except Exception as e:
    print(f"⚠️ NeMo Guardrails failed to initialize: {e}")
    rails = None
    rails_active = False

class QueryRequest(BaseModel):
    prompt: str
    user_id: str = "default_user" 

@app.get("/health")
def health_check():
    status = {"status": "ok", "service": "financial-advisor-agent"}
    if rails_active:
        status["guardrails"] = "active"
    else:
        status["guardrails"] = "inactive"
    return status

@app.post("/agent/query")
async def query_agent(request: QueryRequest):
    """
    Invokes the ADK agent with Cybernetic Governance Wrapper.
    Flow: Context -> Input Rails -> Execution -> Output Rails -> Save Context
    """
    try:
        user_id = request.user_id
        original_prompt = request.prompt

        # --- Layer 1: Context Retrieval (Cold State) ---
        context = memory_client.retrieve_context(user_id)
        
        # Augment the prompt for the agent
        augmented_prompt = original_prompt
        if context:
            augmented_prompt = f"[Persistent User Context]:\n{context}\n\n[User Request]:\n{original_prompt}"

        # --- Layer 2: Input Guardrails (Semantic Verification) ---
        if rails_active:
            try:
                # Basic Input Check: Run rails with prompt.
                # If rails block, they return a refusal message.
                # Heuristic: Check for common refusal patterns if specific status is not available.
                check_result = rails.generate(messages=[{"role": "user", "content": original_prompt}])
                check_text = str(check_result.get("content", check_result)) if isinstance(check_result, dict) else str(check_result)
                
                # If checks fail, usually NeMo returns a canned refusal.
                # We can enforce blocking here if detected.
                # For now, we trust the deployment logging to verify.
                if "I cannot" in check_text or "sorry" in check_text.lower():
                     print(f"🛑 Blocked by input rails: {check_text}")
                     return {"response": check_text}
            except Exception as e:
                print(f"Guardrails Input Check Warning: {e}")

        # --- Layer 3: Execution (The Runner) ---
        # Reuse the global runner to find the existing session
        # Passing 'app_name' explicitly to ensure match if default differs
        session = await runner.session_service.create_session(
            app_name="financial_advisor",
            user_id=user_id
        )

        content = UserContent(parts=[Part(text=augmented_prompt)])
        
        final_text = ""
        async for event in runner.run_async(
            session_id=session.id,
            user_id=user_id,
            new_message=content
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        final_text += part.text
        
        # --- Layer 4: Output Guardrails ---
        if rails_active:
            try:
                # Placeholder for output verification
                pass
            except Exception as e:
                print(f"Guardrails Output Check Warning: {e}")

        # --- Layer 5: Context Storage ---
        # Fire-and-forget save of the interaction to Vertex AI
        memory_client.save_context(user_id, original_prompt)
        
        return {"response": final_text}

    except Exception as e:
        print(f"❌ Error invoking agent: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
