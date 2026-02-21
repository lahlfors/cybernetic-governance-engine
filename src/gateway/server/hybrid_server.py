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
from src.governed_financial_advisor.tools.market_data_tool import get_market_data

# Configure Logging via Telemetry (Centralized Control)
from src.governed_financial_advisor.utils.telemetry import configure_telemetry, logger
configure_telemetry()

# Global Resources Initialization
rails = initialize_rails()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Hybrid Gateway Starting...")
    yield
    # Shutdown
    logger.info("🛑 Hybrid Gateway Shutting Down...")
    await opa_client.close()

# --- 2. Initialize FastAPI App ---
app = FastAPI(title="Governed Financial Advisor Gateway (Hybrid)", lifespan=lifespan)

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    
    def server_request_hook(span, scope):
        if not span or not span.is_recording():
            return
        # Extract headers from ASGI scope
        headers = dict((k.decode("utf-8").lower(), v.decode("utf-8")) for k, v in scope.get("headers", []))
        session_id = headers.get("x-session-id")
        if session_id:
            span.set_attribute("langfuse.session.id", session_id)
            
    FastAPIInstrumentor.instrument_app(app, server_request_hook=server_request_hook)
    logger.info("✅ FastAPI OpenTelemetry instrumentation activated with Session IDs.")
except ImportError:
    logger.warning("⚠️ FastAPIInstrumentor not found, skipping framework instrumentation.")

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
    return market_service.check_status(symbol)

@mcp.tool()
async def get_market_sentiment(symbol: str) -> str:
    """Fetches real-time market sentiment and news for a given ticker symbol using AlphaVantage."""
    logger.info(f"Tool Call: get_market_sentiment({symbol})")
    return await market_service.get_sentiment(symbol)

@mcp.tool()
async def get_market_data(ticker: str) -> str:
    """Fetches comprehensive market data for a given ticker using yfinance."""
    logger.info(f"Tool Call: get_market_data({ticker})")
    # Wrap synchronous tool if necessary, but FastMCP supports async/sync
    # get_market_data is likely sync, correct?
    # FunctionTool wrapper in ADK can handle it if we just call it.
    # But here we are in FastAPI/MCP. FastMCP handles sync functions in threadpool usually?
    # Let's assume yes or make it async if needed.
    # The original tool is sync.
    return get_market_data(ticker)

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
        messages = []
        for m in request.messages:
            role = m.role
            if role == "assistant":
                role = "bot"
            messages.append({"role": role, "content": m.content})

        # Inject system instruction if provided (as first message)
        if request.system_instruction:
            if not messages or messages[0]["role"] != "system":
                messages.insert(0, {"role": "system", "content": request.system_instruction})

        # 1. Guardrails Check (Input Rails Only - PII Masking & Safety)
        res = await rails.generate_async(
            messages=messages,
            options={"rails": ["input"]}
        )

        bot_response = ""
        if hasattr(res, "response") and isinstance(res.response, list) and len(res.response) > 0:
            bot_response = res.response[0].get("content", "")
        # Fallback for dictionaries if NeMo changes API
        elif isinstance(res, dict) and "response" in res and len(res["response"]) > 0:
            bot_response = res["response"][0].get("content", "")

        # If NeMo generated a bot response during the input rail phase, 
        # it means a guardrail blocked the input and provided a canned refusal.
        if bot_response:
            final_response = bot_response
        else:
            # 2. Native LLM Call (Bypassing NeMo Dialog Logic)
            from src.gateway.governance.nemo.vllm_client import VLLMLLM
            from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

            llm = VLLMLLM()
            
            # Convert dict messages to Langchain messages
            lc_messages = []
            for m in messages:
                if m["role"] == "system":
                    lc_messages.append(SystemMessage(content=m["content"]))
                elif m["role"] == "assistant" or m["role"] == "bot":
                    lc_messages.append(AIMessage(content=m["content"]))
                else:
                    lc_messages.append(HumanMessage(content=m["content"]))
                    
            # Generate completion
            llm_response = await llm._acall(lc_messages)
            response_text = llm_response

            # 3. Guardrails Check (Output Rails - Unsafe Dialogues & PII Masking)
            messages.append({"role": "bot", "content": response_text})
            output_res = await rails.generate_async(
                messages=messages,
                options={"rails": ["output"]}
            )
            
            if hasattr(output_res, "response") and isinstance(output_res.response, list) and len(output_res.response) > 0:
                out_content = output_res.response[0].get("content", "")
                final_response = out_content if out_content else response_text
            elif isinstance(output_res, dict) and "response" in output_res and len(output_res["response"]) > 0:
                out_content = output_res["response"][0].get("content", "")
                final_response = out_content if out_content else response_text
            else:
                final_response = response_text

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
                        "content": final_response
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": len(final_response) // 4,
                "total_tokens": len(final_response) // 4
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
            "execute_trade_action": execute_trade_action,
            "get_market_data": get_market_data
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

        elif request.tool_name == "get_market_data":
             output = func(request.params.get("ticker"))

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
    
    # Determine Log Config
    # Determine Log Config
    # Force Enable Logging for Debugging
    log_config = None
    # if os.getenv("ENABLE_LOGGING", "true").lower() != "true":
    #     # Explicitly disable uvicorn logging
    #     log_config = {
    #         "version": 1,
    #         "disable_existing_loggers": False,
    #         "handlers": {
    #             "null": {"class": "logging.NullHandler"}
    #         },
    #         "loggers": {
    #             "uvicorn": {"level": "CRITICAL", "handlers": ["null"], "propagate": False},
    #             "uvicorn.error": {"level": "CRITICAL", "handlers": ["null"], "propagate": False},
    #             "uvicorn.access": {"level": "CRITICAL", "handlers": ["null"], "propagate": False},
    #         },
    #         "root": {"level": "CRITICAL", "handlers": ["null"]}
    #     }
    
    # Configure root logger to INFO/DEBUG
    logging.basicConfig(level=logging.INFO)
    logger.info("DEBUG: forced logging in hybrid_server.py")
        
    uvicorn.run(app, host="0.0.0.0", port=http_port, log_config=log_config)
