import asyncio
import logging
import json
import os
import sys
from typing import List, Optional, Dict, Any, Union

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

# Adjust path so we can import from src
sys.path.append(".")

from mcp.server.fastmcp import FastMCP

# Reuse existing core logic
from src.gateway.core.llm import HybridClient
from src.gateway.core.policy import OPAClient
from src.gateway.core.tools import execute_trade, TradeOrder
from src.gateway.core.market import market_service
from src.governed_financial_advisor.governance.consensus import consensus_engine
from src.governed_financial_advisor.governance.safety import safety_filter

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Gateway.Hybrid")

# --- 1. Initialize FastAPI App ---
app = FastAPI(title="Governed Financial Advisor Gateway (Hybrid)")

# --- 2. Initialize MCP Server ---
mcp = FastMCP("Governed Gateway")
opa_client = OPAClient()
# We initialize HybridClient lazily or globally
llm_client = HybridClient() # Uses env vars

# --- 3. Governance Logic (Shared) ---
async def enforce_governance(tool_name: str, params: dict):
    """
    Centralized Governance Check (OPA, Safety, Consensus).
    """
    # 1. OPA Check
    if tool_name not in ["check_market_status", "verify_content_safety"]:
        payload = params.copy()
        payload['action'] = tool_name
        decision = await opa_client.evaluate_policy(payload)

        if decision == "DENY":
            raise PermissionError(f"OPA Policy Violation: Action '{tool_name}' DENIED.")
        if decision == "MANUAL_REVIEW":
            logger.critical(f"MANUAL REVIEW REQUIRED for {tool_name}")
            raise PermissionError("Manual Review Triggered - Admin Notified.")

    # 2. Safety Filter (Trade Only)
    if tool_name == "execute_trade":
        cbf_result = safety_filter.verify_action(tool_name, params)
        if cbf_result.startswith("UNSAFE"):
             raise ValueError(f"Safety Filter Blocked: {cbf_result}")

        # 3. Consensus Engine
        amount = params.get("amount", 0)
        symbol = params.get("symbol", "UNKNOWN")
        consensus = await consensus_engine.check_consensus(tool_name, amount, symbol)

        if consensus["status"] == "REJECT":
             raise PermissionError(f"Consensus Rejected: {consensus['reason']}")
        if consensus["status"] == "ESCALATE":
             raise PermissionError(f"Consensus Escalation: {consensus['reason']}")

    return True

# --- 4. MCP Tools Definition ---

@mcp.tool()
async def check_market_status(symbol: str) -> str:
    """Checks the current market status and price for a given ticker symbol."""
    logger.info(f"Tool Call: check_market_status({symbol})")
    return market_service.check_status(symbol)

@mcp.tool()
async def get_market_sentiment(symbol: str) -> str:
    """Fetches real-time market sentiment and news for a given ticker symbol using AlphaVantage."""
    logger.info(f"Tool Call: get_market_sentiment({symbol})")
    return await market_service.get_sentiment(symbol)

@mcp.tool()
async def verify_content_safety(text: str) -> str:
    """Verifies if the provided text content is safe (Jailbreak detection)."""
    logger.info("Tool Call: verify_content_safety")
    if "jailbreak" in text.lower() or "ignore previous" in text.lower():
         return "BLOCKED: Semantic Safety Violation (Jailbreak Pattern)"
    return "SAFE"

@mcp.tool()
async def evaluate_policy(action: str, description: str = None, dry_run: bool = True, **kwargs) -> str:
    """Evaluates an action against OPA policy without executing it."""
    logger.info(f"Tool Call: evaluate_policy(action={action})")
    params = kwargs.copy()
    params['action'] = action
    params['description'] = description
    params['dry_run'] = dry_run

    try:
        decision = await opa_client.evaluate_policy(params)
        if decision == "ALLOW": return "APPROVED: Action matches policy."
        elif decision == "DENY": return "DENIED: Policy Violation."
        elif decision == "MANUAL_REVIEW": return "MANUAL_REVIEW: Requires human approval."
        else: return f"UNKNOWN: {decision}"
    except Exception as e:
        logger.error(f"Policy Check Error: {e}")
        return f"ERROR: {e}"

@mcp.tool()
async def execute_trade_action(symbol: str, amount: float, currency: str, transaction_id: str = None, trader_id: str = "agent_001", trader_role: str = "junior", dry_run: bool = False) -> str:
    """Executes a financial trade under strict governance."""
    logger.info(f"Tool Call: execute_trade({symbol}, {amount})")
    import uuid
    if not transaction_id: transaction_id = str(uuid.uuid4())

    params = {
        "symbol": symbol, "amount": amount, "currency": currency,
        "transaction_id": transaction_id, "trader_id": trader_id,
        "trader_role": trader_role, "dry_run": dry_run
    }

    try:
        await enforce_governance("execute_trade", params)
    except Exception as e:
        return f"BLOCKED: {e}"

    if dry_run:
        return "DRY_RUN: APPROVED by OPA, Safety, and Consensus."

    safety_filter.update_state(amount)

    try:
        order = TradeOrder(**params)
        result = await execute_trade(order)
        return result
    except Exception as e:
        logger.error(f"Execution Error: {e}")
        return f"ERROR: {e}"

# --- 5. Mount MCP Server ---
# We mount the MCP SSE app at the root (handling /sse and /messages)
# Note: FastMCP.sse_app() returns a Starlette app.
logger.info("Mounting MCP SSE App at /sse_app...")
# We mount at /mcp to avoid conflict with root routes.
# Clients must connect to /mcp/sse
app.mount("/mcp", mcp.sse_app())

@app.get("/health")
async def health_check():
    return {"status": "ok", "mode": "hybrid"}

# --- 6. Chat Endpoint (OpenAI Compatible) ---

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: Optional[str] = "default"
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    stream: Optional[bool] = False
    system_instruction: Optional[str] = None
    guided_json: Optional[Dict[str, Any]] = None
    guided_regex: Optional[str] = None
    guided_choice: Optional[List[str]] = None

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """
    OpenAI-compatible Chat Completion Endpoint.
    Routes to vLLM via HybridClient.
    """
    logger.info(f"Chat Request: Model={request.model} Stream={request.stream}")

    # Extract last user message or build prompt
    # HybridClient expects a single prompt usually, but can handle lists?
    # Checking HybridClient.generate: expects (prompt: str, system_instruction: str, ...)
    # So we need to collapse messages or extract the last one.

    # Strategy: Use last user message as prompt. System message as system_instruction.
    system_instruction = request.system_instruction
    prompt = ""

    for msg in request.messages:
        if msg.role == "system":
            system_instruction = msg.content
        elif msg.role == "user":
            prompt = msg.content # Simplistic: take last user message

    # Prepare kwargs
    kwargs = {}
    if request.temperature: kwargs['temperature'] = request.temperature
    if request.guided_json: kwargs['guided_json'] = request.guided_json
    if request.guided_regex: kwargs['guided_regex'] = request.guided_regex
    if request.guided_choice: kwargs['guided_choice'] = request.guided_choice
    if request.model: kwargs['model'] = request.model

    # Mode determination
    mode = "chat"
    if "verifier" in (request.model or ""): mode = "verifier"

    try:
        if request.stream:
            # TODO: HybridClient currently returns full response string in the code I read.
            # I need to check if HybridClient supports yielding.
            # src/gateway/core/llm.py: `if is_verifier: ... return full_response else: stream = response ...`
            # Yes, it supports streaming! But the current generate method implementation I read *consumes* the stream and returns full string!
            # See line: `full_response = "".join(collected_content)` in `src/gateway/core/llm.py`.
            # I need to update HybridClient to yield if I want true streaming.
            # For now, I will fake streaming or just return JSON.
            pass

        # Call HybridClient
        response_text = await llm_client.generate(
            prompt=prompt,
            system_instruction=system_instruction,
            mode=mode,
            **kwargs
        )

        # Build OpenAI Response
        import time
        resp_id = f"chatcmpl-{int(time.time())}"

        response_data = {
            "id": resp_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": len(prompt) // 4,
                "completion_tokens": len(response_text) // 4,
                "total_tokens": (len(prompt) + len(response_text)) // 4
            }
        }

        return JSONResponse(content=response_data)

    except Exception as e:
        logger.error(f"Chat Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
