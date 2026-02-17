import asyncio
import logging
import json
import os
import sys
from typing import List, Optional, Dict, Any, Union
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

# Adjust path so we can import from src
sys.path.append(".")

from mcp.server.fastmcp import FastMCP

# Core logic
from src.gateway.core.tools import execute_trade, TradeOrder
from src.gateway.core.market import market_service
from src.gateway.governance.singletons import symbolic_governor, opa_client
from src.gateway.governance.symbolic_governor import GovernanceError
from src.gateway.governance.nemo.manager import initialize_rails, validate_with_nemo

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Gateway.HybridServer")

from src.governed_financial_advisor.utils.telemetry import configure_telemetry
configure_telemetry()

# --- 1. Initialize Global Resources ---
rails = initialize_rails()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Hybrid Gateway Starting...")
    yield
    # Shutdown
    logger.info("🛑 Hybrid Gateway Shutting Down...")
    await opa_client.close()
    await market_service.close()

# --- 2. Initialize FastAPI App ---
app = FastAPI(title="Governed Financial Advisor Gateway (Hybrid)", lifespan=lifespan)

# --- 3. Initialize MCP Server ---
mcp = FastMCP("Governed Gateway")

async def enforce_governance(tool_name: str, params: dict):
    """
    Centralized Governance Check (OPA, Safety, Consensus).
    """
    # 1. Neuro-Symbolic Governance Layer
    # Enforces SR 11-7 (Rules) and ISO 42001 (Policy/Process)
    if tool_name not in ["check_market_status", "verify_content_safety"]:
        try:
            await symbolic_governor.govern(tool_name, params)
        except GovernanceError as e:
            logger.warning(f"🛡️ Symbolic Governor BLOCKED {tool_name}: {e}")
            raise PermissionError(f"Governance Blocked: {e}")

    return True

# --- 4. MCP Tools Definition ---

@mcp.tool()
async def check_safety_constraints(target_tool: str, target_params: dict, risk_profile: str = "Medium") -> str:
    """
    Meta-tool: Runs a dry-run of the Symbolic Governor on a proposed action.
    Used by the Evaluator Agent (System 3) to verify safety before execution.
    """
    logger.info(f"🔍 Evaluator verifying proposed action: {target_tool} (Risk: {risk_profile})")
    
    verification_params = target_params.copy()
    verification_params["risk_profile"] = risk_profile
    
    violations = await symbolic_governor.verify(target_tool, verification_params)

    if not violations:
        return "APPROVED: No violations detected."
    else:
        return f"REJECTED: {'; '.join(violations)}"

@mcp.tool()
async def trigger_safety_intervention(reason: str) -> str:
    """
    Emergency Stop: Locks the system via Redis when a violation is detected.
    """
    logger.critical(f"🛑 SAFETY INTERVENTION TRIGGERED: {reason}")
    from src.governed_financial_advisor.infrastructure.redis_client import redis_client
    redis_client.set("safety_violation", reason)
    return "INTERVENTION_ACK: System Locked."

@mcp.tool()
async def check_market_status(symbol: str) -> str:
    """Checks the current market status and price for a given ticker symbol."""
    logger.info(f"Tool Call: check_market_status({symbol})")
    return await market_service.check_status_async(symbol)

@mcp.tool()
async def get_market_sentiment(symbol: str) -> str:
    """Fetches real-time market sentiment and news for a given ticker symbol using AlphaVantage."""
    logger.info(f"Tool Call: get_market_sentiment({symbol})")
    return await market_service.get_sentiment(symbol)

@mcp.tool()
async def verify_content_safety(text: str) -> str:
    """Verifies if the provided text content is safe using NeMo Guardrails."""
    logger.info("Tool Call: verify_content_safety")
    is_safe, response = await validate_with_nemo(text, rails)
    if not is_safe:
        return f"BLOCKED: {response}"
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

    symbolic_governor.safety_filter.update_state(amount)

    try:
        order = TradeOrder(**params)
        result = await execute_trade(order)
        return result
    except Exception as e:
        logger.error(f"Execution Error: {e}")
        symbolic_governor.safety_filter.rollback_state(amount)
        return f"ERROR: {e}"

# --- 5. Mount MCP Server ---
logger.info("Mounting MCP SSE App at /sse_app...")
app.mount("/mcp", mcp.sse_app())

@app.get("/health")
async def health_check():
    return {"status": "ok", "mode": "hybrid", "nemo": "active"}

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
    OpenAI-compatible Chat Completion Endpoint using NeMo Guardrails.
    Routes to VLLM via NeMo (configured in config/rails or manager.py).
    """
    logger.info(f"Chat Request: Model={request.model} Stream={request.stream}")

    try:
        # Convert Pydantic messages to dicts for NeMo
        messages = [{"role": m.role, "content": m.content} for m in request.messages]

        # Inject system instruction if provided (as first message)
        if request.system_instruction:
            if not messages or messages[0]["role"] != "system":
                messages.insert(0, {"role": "system", "content": request.system_instruction})

        # Generate with NeMo (enforces rails)
        # Using generate_async calls NeMo's LLM (VLLM) with the conversation history
        # and applies Input/Output rails.
        res = await rails.generate_async(messages=messages)

        response_text = ""
        # Handle NeMo response variations (Dict or String)
        if isinstance(res, dict) and "content" in res:
            response_text = res["content"]
        elif isinstance(res, str):
            response_text = res
        else:
             # Fallback
             response_text = str(res)

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
                "prompt_tokens": 0,
                "completion_tokens": len(response_text) // 4,
                "total_tokens": len(response_text) // 4
            }
        }

        return JSONResponse(content=response_data)

    except Exception as e:
        logger.error(f"Chat Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 7. Tool Execution Endpoint (HTTP) ---
# Supports GatewayClient (HTTP) calls

class ToolExecutionRequest(BaseModel):
    tool_name: str
    params: Dict[str, Any]

@app.post("/tools/execute")
async def execute_tool_endpoint(request: ToolExecutionRequest):
    """
    Executes a named tool directly via HTTP.
    """
    logger.info(f"Tool Execution Request: {request.tool_name}")
    
    try:
        output = None
        
        # Dispatcher Mapping
        tool_map = {
            "check_safety_constraints": check_safety_constraints,
            "trigger_safety_intervention": trigger_safety_intervention,
            "check_market_status": check_market_status,
            "get_market_sentiment": get_market_sentiment,
            "verify_content_safety": verify_content_safety,
            "evaluate_policy": evaluate_policy,
            "execute_trade_action": execute_trade_action
        }

        if request.tool_name not in tool_map:
             raise HTTPException(status_code=404, detail=f"Tool '{request.tool_name}' not found")

        func = tool_map[request.tool_name]

        # Argument binding logic
        if request.tool_name == "check_safety_constraints":
             target_tool = request.params.get("target_tool")
             target_params = request.params.get("target_params") or {}
             risk_profile = request.params.get("risk_profile", "Medium")
             output = await func(target_tool, target_params, risk_profile)

        elif request.tool_name == "trigger_safety_intervention":
             output = await func(request.params.get("reason", "Unknown"))

        elif request.tool_name == "check_market_status":
             output = await func(request.params.get("symbol"))

        elif request.tool_name == "get_market_sentiment":
             output = await func(request.params.get("symbol"))

        elif request.tool_name == "verify_content_safety":
             output = await func(request.params.get("text", ""))

        else:
             # evaluate_policy and execute_trade_action accept kwargs
             output = await func(**request.params)
        
        return {"status": "SUCCESS", "output": str(output)}

    except Exception as e:
        logger.error(f"Tool Execution Error: {e}")
        return {"status": "ERROR", "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    http_port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=http_port)
