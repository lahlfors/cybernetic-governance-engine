from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uvicorn
import logging
import os

# Initialize Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SidecarGuard")

app = FastAPI(title="Neuro-Cybernetic Guard Sidecar")

class ActionRequest(BaseModel):
    action: str
    context: Dict[str, Any]

class ActionResponse(BaseModel):
    allowed: bool
    reason: Optional[str] = None
    mock_execution: bool = True

# --- Safety Logic ---
# In a real system, this might use NetworkX or complex rules.
# For now, we replicate the "High Risk" blocking logic.

def check_policy_graph(action: str, context: Dict[str, Any]) -> tuple[bool, str]:
    """
    Checks the immutable Policy Graph.
    """
    risk_score = context.get("risk_score", 0.0)

    # 1. Global Blocking Rules (The "Guard")
    if action == "block_transaction":
        # Policy: Only allow blocking if risk is CONFIRMED high (> 0.9)
        # OR if explicitly authorized.
        if risk_score > 0.9:
            return True, "Authorized by High Risk Score"
        else:
             return False, "Policy Violation: Cannot block without High Risk Score (> 0.9)"

    if action == "execute_trade":
        # Policy: Check liquidity / fraud
        if risk_score > 0.5:
            return False, "Policy Violation: Trading halted due to Moderate Risk"

    return True, "Action Allowed"

@app.post("/execute_action", response_model=ActionResponse)
async def execute_action(request: ActionRequest):
    logger.info(f"🛡️ Guard received request: {request.action}")

    # 1. Verify against Policy Graph
    allowed, reason = check_policy_graph(request.action, request.context)

    if not allowed:
        logger.warning(f"⛔ Action BLOCKED: {reason}")
        # Return 403 Forbidden logic
        return ActionResponse(allowed=False, reason=reason)
        # In strict HTTP terms we might return 403, but returning JSON allows
        # the agent to reason about *why* it failed without exception handling overhead.

    # 2. Mock Execution (The Sidecar executes on behalf of the agent)
    # In a real scenario, this sidecar would have the API_KEY to call the Banking Core.
    logger.info(f"✅ Action ALLOWED. Executing upstream: {request.action}")

    return ActionResponse(allowed=True, reason=reason)

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 9000))
    uvicorn.run(app, host="0.0.0.0", port=port)
