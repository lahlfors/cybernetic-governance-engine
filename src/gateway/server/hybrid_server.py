"""
Refactored Gateway Server (HTTP/MCP Only)
- Removes gRPC Server (depreciated)
- Retains gRPC Client (NeMo)
- Exposes MCP/HTTP Tools
"""
import asyncio
import logging
import json
import os
import sys
from typing import List, Optional, Dict, Any, Union

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
import grpc

# Adjust path so we can import from src
sys.path.append(".")

from mcp.server.fastmcp import FastMCP

# Reuse existing core logic
from src.gateway.core.llm import GatewayClient
from src.gateway.core.policy import OPAClient
from src.gateway.core.tools import execute_trade, TradeOrder
from src.gateway.core.market import market_service
from src.gateway.governance.consensus import consensus_engine
from src.gateway.governance.safety import safety_filter

# NeMo gRPC
from src.gateway.protos import nemo_pb2
from src.gateway.protos import nemo_pb2_grpc

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Gateway.HybridServer")

from src.governed_financial_advisor.utils.telemetry import configure_telemetry
configure_telemetry()

# --- 1. Initialize FastAPI App ---
app = FastAPI(title="Governed Financial Advisor Gateway (HTTP/MCP)")

# --- 2. Initialize MCP Server ---
mcp = FastMCP("Governed Gateway")
opa_client = OPAClient()
# We initialize HybridClient lazily or globally
llm_client = GatewayClient() # Uses env vars

# Initialize NeMo Client (Lazy)
nemo_url = os.getenv("NEMO_URL", "nemo:8000")
nemo_channel = None
nemo_stub = None

def get_nemo_stub():
    global nemo_channel, nemo_stub
    if not nemo_stub:
        logger.info(f"Connecting to NeMo Guardrails at {nemo_url}...")
        nemo_channel = grpc.aio.insecure_channel(nemo_url)
        nemo_stub = nemo_pb2_grpc.NeMoGuardrailsStub(nemo_channel)
    return nemo_stub

# --- 3. Governance Logic (Shared) ---
# Initialize Neuro-Symbolic Governor
from src.gateway.governance import SymbolicGovernor, GovernanceError
symbolic_governor = SymbolicGovernor(
    opa_client=opa_client,
    safety_filter=safety_filter,
    consensus_engine=consensus_engine
)

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
    return market_service.check_status(symbol)

@mcp.tool()
async def get_market_sentiment(symbol: str) -> str:
    """Fetches real-time market sentiment and news for a given ticker symbol using AlphaVantage."""
    logger.info(f"Tool Call: get_market_sentiment({symbol})")
    return await market_service.get_sentiment(symbol)

@mcp.tool()
async def verify_content_safety(text: str) -> str:
    """Verifies if the provided text content is safe (Jailbreak detection) using NeMo Guardrails."""
    logger.info("Tool Call: verify_content_safety")

    # 1. Basic Heuristic Check
    if "jailbreak" in text.lower() or "ignore previous" in text.lower():
         return "BLOCKED: Semantic Safety Violation (Jailbreak Pattern)"

    # 2. Remote NeMo Check via gRPC
    try:
        stub = get_nemo_stub()
        request = nemo_pb2.VerifyRequest(input=text)
        # Timeout to prevent hanging
        response = await asyncio.wait_for(stub.Verify(request), timeout=5.0)

        if response.status == "SUCCESS":
             # If NeMo returns SUCCESS, we assume it's safe, or we check response content if needed.
             # NeMo might return a modified safe response.
             return "SAFE"
        else:
             return f"BLOCKED: {response.response}"

    except asyncio.TimeoutError:
        logger.error("NeMo Service Timeout")
        return "BLOCKED: Safety Service Timeout"
    except grpc.RpcError as e:
        logger.error(f"NeMo gRPC Failed: {e}")
        return "BLOCKED: Safety Service Unavailable"
    except Exception as e:
         logger.error(f"NeMo Verification Error: {e}")
         return f"BLOCKED: Safety Error {e}"

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
    return {"status": "ok", "mode": "http-mcp"}

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

# --- 7. Tool Execution Endpoint (HTTP) ---
# Supports GatewayClient (HTTP) calls

class ToolExecutionRequest(BaseModel):
    tool_name: str
    params: Dict[str, Any]

@app.post("/tools/execute")
async def execute_tool_endpoint(request: ToolExecutionRequest):
    """
    Executes a named tool directly via HTTP.
    Matches GatewayClient.execute_tool expectations.
    """
    logger.info(f"Tool Execution Request: {request.tool_name}")
    
    try:
        # Dispatch to MCP Tools
        # We can call the decorated functions directly
        output = None
        
        if request.tool_name == "check_safety_constraints":
            # Parse params loosely
            target_tool = request.params.get("target_tool")
            target_params = request.params.get("target_params") or {}
            risk_profile = request.params.get("risk_profile", "Medium")
            output = await check_safety_constraints(target_tool, target_params, risk_profile)
            
        elif request.tool_name == "trigger_safety_intervention":
            reason = request.params.get("reason", "Unknown")
            output = await trigger_safety_intervention(reason)
            
        elif request.tool_name == "check_market_status":
            symbol = request.params.get("symbol")
            if not symbol: raise ValueError("Missing 'symbol'")
            output = await check_market_status(symbol)
            
        elif request.tool_name == "get_market_sentiment":
            symbol = request.params.get("symbol")
            if not symbol: raise ValueError("Missing 'symbol'")
            output = await get_market_sentiment(symbol)
            
        elif request.tool_name == "verify_content_safety":
            text = request.params.get("text", "")
            output = await verify_content_safety(text)
            
        elif request.tool_name == "evaluate_policy":
            # kwargs unpack
            output = await evaluate_policy(**request.params)
            
        elif request.tool_name == "execute_trade_action":
            # kwargs unpack
            output = await execute_trade_action(**request.params)
            
        else:
            raise HTTPException(status_code=404, detail=f"Tool '{request.tool_name}' not found")
        
        return {"status": "SUCCESS", "output": str(output)}

    except Exception as e:
        logger.error(f"Tool Execution Error: {e}")
        return {"status": "ERROR", "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    
    http_port = int(os.getenv("PORT", 8080))
    # Removed gRPC Server initialization
    
    config = uvicorn.Config(app, host="0.0.0.0", port=http_port)
    server = uvicorn.Server(config)
    
    # Run only HTTP server
    asyncio.run(server.serve())
