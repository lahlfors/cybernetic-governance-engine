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

# Reuse existing core logic
from src.gateway.core.llm import GatewayClient
from src.gateway.core.policy import OPAClient
from src.gateway.core.tools import execute_trade, TradeOrder
from src.gateway.core.market import market_service
from src.gateway.governance.consensus import consensus_engine
from src.gateway.governance.safety import safety_filter

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Gateway.HybridServer")

from src.governed_financial_advisor.utils.telemetry import configure_telemetry
configure_telemetry()

# --- 1. Initialize FastAPI App ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await market_service.shutdown()
    market_service.shutdown_sync()

app = FastAPI(title="Governed Financial Advisor Gateway (Hybrid)", lifespan=lifespan)

# --- 2. Initialize MCP Server ---
mcp = FastMCP("Governed Gateway")
opa_client = OPAClient()
# We initialize HybridClient lazily or globally
llm_client = GatewayClient() # Uses env vars

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
    
    # Inject risk profile into params for OPA to see
    # The Governor's 'verify' method eventually calls OPA.
    # We need to ensure 'risk_profile' is in the payload OPA receives.
    # We might need to patch attributes or pass it via context if SymbolicGovernor supports it.
    # For now, let's inject it into target_params as metadata if possible, 
    # or rely on OPAClient updates if we modify SymbolicGovernor.
    
    # Reviewing SymbolicGovernor.verify: it calls opa_client.evaluate_policy(params)
    # So we should add risk_profile to target_params for the check.
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

# --- 8. gRPC Server Implementation ---
import grpc
from src.gateway.protos import gateway_pb2, gateway_pb2_grpc

class GatewayService(gateway_pb2_grpc.GatewayServicer):
    async def Chat(self, request, context):
        """
        gRPC Chat Implementation.
        """
        logger.info(f"gRPC Chat Request: Model={request.model}")
        
        # Extract prompt from messages
        system_instruction = request.system_instruction
        prompt = ""
        for msg in request.messages:
            if msg.role == "system":
                system_instruction = msg.content
            elif msg.role == "user":
                prompt = msg.content

        # Prepare kwargs
        kwargs = {
            "model": request.model,
            "temperature": request.temperature,
            "guided_json": json.loads(request.guided_json) if request.guided_json else None,
            "guided_regex": request.guided_regex if request.guided_regex else None,
            "guided_choice": json.loads(request.guided_choice) if request.guided_choice else None,
            "stream": True # Force stream for gRPC
        }

        mode = "chat"
        if "verifier" in (request.model or "") or request.mode == "verifier":
            mode = "verifier"

        try:
            # Call HybridClient
            # We need to ensure HybridClient supports yielding/streaming if we want true streaming.
            # Current implementation returns full text. We will yield it as one chunk for now.
            response_text = await llm_client.generate(
                prompt=prompt,
                system_instruction=system_instruction,
                mode=mode,
                **kwargs
            )
            
            # Yield response
            yield gateway_pb2.ChatResponse(content=response_text, is_final=True)

        except Exception as e:
            logger.error(f"gRPC Chat Error: {e}")
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)

    async def ExecuteTool(self, request, context):
        """
        gRPC Tool Execution.
        """
        logger.info(f"gRPC Tool Execution: {request.tool_name}")
        try:
            params = json.loads(request.params_json)
            output = None

            # Recycle endpoint logic (refactor eventually to separate service layer)
            if request.tool_name == "check_safety_constraints":
                target_tool = params.get("target_tool")
                target_params = params.get("target_params") or {}
                risk_profile = params.get("risk_profile", "Medium")
                output = await check_safety_constraints(target_tool, target_params, risk_profile)
            
            elif request.tool_name == "trigger_safety_intervention":
                reason = params.get("reason", "Unknown")
                output = await trigger_safety_intervention(reason)
                
            elif request.tool_name == "check_market_status":
                symbol = params.get("symbol")
                output = await check_market_status(symbol)
                
            elif request.tool_name == "get_market_sentiment":
                symbol = params.get("symbol")
                output = await get_market_sentiment(symbol)
                
            elif request.tool_name == "verify_content_safety":
                text = params.get("text", "")
                output = await verify_content_safety(text)
                
            elif request.tool_name == "evaluate_policy":
                output = await evaluate_policy(**params)
                
            elif request.tool_name == "execute_trade_action":
                output = await execute_trade_action(**params)
                
            else:
                context.set_details(f"Tool '{request.tool_name}' not found")
                context.set_code(grpc.StatusCode.NOT_FOUND)
                return gateway_pb2.ToolResponse(status="ERROR", error="Tool not found")

            return gateway_pb2.ToolResponse(output=str(output), status="SUCCESS")

        except Exception as e:
            logger.error(f"gRPC Tool Error: {e}")
            return gateway_pb2.ToolResponse(error=str(e), status="ERROR")

async def serve_grpc():
    server = grpc.aio.server()
    gateway_pb2_grpc.add_GatewayServicer_to_server(GatewayService(), server)
    grpc_port = os.getenv("GATEWAY_GRPC_PORT", "50051")
    server.add_insecure_port(f'[::]:{grpc_port}')
    logger.info(f"🚀 gRPC Server starting on port {grpc_port}...")
    await server.start()
    await server.wait_for_termination()

if __name__ == "__main__":
    import uvicorn
    
    # Run both servers?
    # Option: Run FastAPI in one task, gRPC in another.
    # Uvicorn run() is blocking. We can use Config and Server.serve() in a loop.
    
    http_port = int(os.getenv("PORT", 8080))
    grpc_port = int(os.getenv("GATEWAY_GRPC_PORT", 50051))
    
    config = uvicorn.Config(app, host="0.0.0.0", port=http_port)
    server = uvicorn.Server(config)
    
    async def main():
        # Start gRPC
        grpc_task = asyncio.create_task(serve_grpc())
        # Start HTTP
        http_task = asyncio.create_task(server.serve())
        
        await asyncio.gather(grpc_task, http_task)
        
    asyncio.run(main())
