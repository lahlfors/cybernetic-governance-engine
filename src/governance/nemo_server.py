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

try:
    config = RailsConfig.from_path(RAILS_CONFIG_PATH)
    rails = LLMRails(config)
    logger.info(f"✅ NeMo Guardrails loaded from {RAILS_CONFIG_PATH}")
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
        raise HTTPException(status_code=500, detail="NeMo Guardrails not initialized")

    try:
        # Generate response using NeMo
        # This runs the Colang flows defined in config
        response = await rails.generate_async(
            messages=[{"role": "user", "content": request.input}]
        )

        # In a real output rail scenario, we might pass the bot's response as input
        # For now, we return the processed response
        return {"response": response}

    except Exception as e:
        logger.error(f"Guardrail execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "ok", "rails_loaded": rails is not None}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
