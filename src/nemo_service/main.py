import logging
import os
import sys
from typing import Any

from fastapi import FastAPI, HTTPException
from nemoguardrails import LLMRails, RailsConfig
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NeMoService")

app = FastAPI(title="NeMo Guardrails Service")

# Load Rails Config relative to this file
RAILS_CONFIG_PATH = os.getenv("RAILS_CONFIG_PATH", os.path.join(os.path.dirname(__file__), "rails"))

rails = None

def load_nemo_rails():
    global rails
    try:
        if os.path.exists(RAILS_CONFIG_PATH):
            logger.info(f"🔄 Loading NeMo Guardrails from {RAILS_CONFIG_PATH}...")
            config = RailsConfig.from_path(RAILS_CONFIG_PATH)
            rails = LLMRails(config)
            logger.info(f"✅ NeMo Guardrails loaded successfully.")
        else:
            logger.warning(f"⚠️ Rails config not found at {RAILS_CONFIG_PATH}")
    except Exception as e:
        logger.error(f"❌ Failed to load NeMo Guardrails: {e}")
        rails = None

# Load on startup
load_nemo_rails()

class GuardrailRequest(BaseModel):
    input: str
    context: dict[str, Any] | None = {}

@app.post("/v1/guardrails/check")
async def check_guardrails(request: GuardrailRequest):
    """
    Endpoint to check input against NeMo Guardrails.
    Returns the response content (modified if blocked).
    """
    if not rails:
        raise HTTPException(status_code=503, detail="NeMo Guardrails not initialized")

    try:
        # Generate response using NeMo
        response = await rails.generate_async(
            messages=[{"role": "user", "content": request.input}]
        )

        # If response is blocked, NeMo usually returns the "refusal" message defined in Colang
        content = response.response[0]["content"] if response.response else ""

        return {
            "response": content,
            "blocked": False # We might need to infer this from content or metadata if NeMo exposes it
            # For now, the Agent will use heuristics on the content strings.
        }

    except Exception as e:
        logger.error(f"Guardrail execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    if rails is None:
        raise HTTPException(status_code=503, detail="Rails not loaded")
    return {"status": "ok", "rails_loaded": True}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
