import logging
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.context import streaming_handler_var
from pydantic import BaseModel

# Import OTel Exporter
from governed_financial_advisor.infrastructure.telemetry.nemo_exporter import NeMoOTelCallback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NeMoSidecar")

app = FastAPI()

# Load Rails Config
# Config is likely at /app/config/rails in Docker, or relative locally
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "../../../config/rails")
if not os.path.exists(DEFAULT_CONFIG_PATH):
    # Fallback for Docker where config might be at /app/config/rails
    DEFAULT_CONFIG_PATH = "/app/config/rails"

rails = None
try:
    if os.path.exists(DEFAULT_CONFIG_PATH):
        config = RailsConfig.from_path(DEFAULT_CONFIG_PATH)
        rails = LLMRails(config)
        logger.info(f"✅ NeMo Guardrails loaded from {DEFAULT_CONFIG_PATH}")
    else:
        logger.warning(f"⚠️ Rails config not found at {DEFAULT_CONFIG_PATH}")
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
        raise HTTPException(status_code=503, detail="NeMo Guardrails not initialized")

    try:
        # Initialize OTel Callback
        handler = NeMoOTelCallback()
        token = streaming_handler_var.set(handler)

        try:
            # Generate response using NeMo with OTel tracking
            response = await rails.generate_async(
                messages=[{"role": "user", "content": request.input}],
                streaming_handler=handler
            )
            
            # Extract content strictly
            content = ""
            if response and response.response:
                content = response.response[0]["content"]

            return {
                "response": content
            }
        finally:
            streaming_handler_var.reset(token)

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
