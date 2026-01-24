import logging
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from nemoguardrails import LLMRails, RailsConfig
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NeMoSidecar")

app = FastAPI()

# Load Rails Config
RAILS_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "rails")

rails = None
try:
    if os.path.exists(RAILS_CONFIG_PATH):
        config = RailsConfig.from_path(RAILS_CONFIG_PATH)
        rails = LLMRails(config)
        logger.info(f"✅ NeMo Guardrails loaded from {RAILS_CONFIG_PATH}")
    else:
        logger.warning(f"⚠️ Rails config not found at {RAILS_CONFIG_PATH}")
except Exception as e:
    logger.error(f"❌ Failed to load NeMo Guardrails: {e}")
    rails = None

class GuardrailRequest(BaseModel):
    input: str
    context: dict[str, Any] | None = {}

@app.post("/v1/guardrails/check")
async def check_guardrails(request: GuardrailRequest):
    """
    Endpoint to check input/output against NeMo Guardrails.
    """
    if not rails:
        # Fail Open/Closed decision: For sidecar, strict mode -> 500
        # If rails didn't load, we can't guarantee safety.
        raise HTTPException(status_code=503, detail="NeMo Guardrails not initialized")

    try:
        # Generate response using NeMo
        # This runs the Colang flows defined in config
        response = await rails.generate_async(
            messages=[{"role": "user", "content": request.input}]
        )

        # Structure the response
        return {
            "response": response.response[0]["content"] if response.response else "",
            # Include metadata if supported by version
        }

    except Exception as e:
        logger.error(f"Guardrail execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint for Docker Compose."""
    if rails is None:
        raise HTTPException(status_code=503, detail="Rails not loaded")
    return {"status": "ok", "rails_loaded": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
