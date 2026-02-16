"""
Gateway Server: REST API (FastAPI)
Replaces gRPC service with HTTP/JSON interface for Cloud Run.
"""

import json
import logging
import os
import sys
import time
from typing import List, Optional, Dict, Any, Union

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from pythonjsonlogger import jsonlogger
from opentelemetry import trace

# Adjust path so we can import from src
sys.path.append(".")

from src.gateway.core.llm import HybridClient
from src.gateway.core.policy import OPAClient
from src.gateway.core.tools import execute_trade, TradeOrder
from src.gateway.core.market import market_service

# Import Governance Logic
from src.governed_financial_advisor.governance.consensus import consensus_engine
from src.governed_financial_advisor.governance.safety import safety_filter
from src.gateway.governance.nemo.manager import NeMoManager

# --- Logging Setup ---
logger = logging.getLogger("Gateway.Server")
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter('%(timestamp)s %(severity)s %(name)s %(message)s')
logHandler.setFormatter(formatter)
logging.basicConfig(level=logging.INFO, handlers=[logHandler])

tracer = trace.get_tracer("gateway.server")

# --- App Definition ---
app = FastAPI(title="Governed Financial Advisor Gateway", version="2.0.0")

# --- Initialization ---
# We initialize clients globally or in lifespan
llm_client = HybridClient()
opa_client = OPAClient()
nemo_manager = NeMoManager()

logger.info("Gateway Service Initialized.")

# --- Pydantic Models ---

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    model: Optional[str] = "default"
    temperature: Optional[float] = 0.0
    system_instruction: Optional[str] = None
    mode: Optional[str] = "chat"
    guided_json: Optional[Dict[str, Any]] = None
    guided_regex: Optional[str] = None
    guided_choice: Optional[List[str]] = None

class ChatResponse(BaseModel):
    content: str
    is_final: bool = True
    input_tokens: Optional[int] = 0
    output_tokens: Optional[int] = 0

class ToolRequest(BaseModel):
    tool_name: str
    params: Dict[str, Any]

class ToolResponse(BaseModel):
    status: str # SUCCESS, BLOCKED, ERROR
    output: Optional[str] = None
    error: Optional[str] = None

# --- Routes ---

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    LLM Proxy Endpoint.
    """
    logger.info(f"Received Chat Request: Mode={request.mode}")

    kwargs = {}
    if request.temperature is not None:
        kwargs['temperature'] = request.temperature
    if request.guided_json:
        kwargs['guided_json'] = request.guided_json
    if request.guided_regex:
        kwargs['guided_regex'] = request.guided_regex
    if request.guided_choice:
        kwargs['guided_choice'] = request.guided_choice

    try:
        # Extract prompt from last message
        if not request.messages:
            raise HTTPException(status_code=400, detail="No messages provided")

        prompt_text = request.messages[-1].content

        full_response = await llm_client.generate(
            prompt=prompt_text,
            system_instruction=request.system_instruction,
            mode=request.mode,
            **kwargs
        )

        return ChatResponse(content=full_response)

    except Exception as e:
        logger.error(f"LLM Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tools/execute", response_model=ToolResponse)
async def execute_tool_endpoint(request: ToolRequest):
    """
    Executes a tool with strict governance (OPA, Safety, Consensus).
    """
    start_time = time.time()
    tool_name = request.tool_name
    params = request.params

    logger.info(f"Received Tool Request: {tool_name}")

    # 1. Governance Tax (OPA)
    current_latency_ms = (time.time() - start_time) * 1000

    payload = params.copy()
    payload['action'] = tool_name

    try:
        decision = await opa_client.evaluate_policy(payload, current_latency_ms=current_latency_ms)

        if decision == "DENY":
            return ToolResponse(status="BLOCKED", error="OPA Policy Violation")

        if decision == "MANUAL_REVIEW":
             logger.critical(f"MANUAL REVIEW REQUIRED for {tool_name} | Params: {params}")
             return ToolResponse(status="BLOCKED", error="Manual Review Triggered - Admin Notified.")

    except Exception as e:
        logger.error(f"OPA Check Failed: {e}")
        # Fail closed
        return ToolResponse(status="ERROR", error=f"Policy Check Error: {str(e)}")

    # 2. Safety & Consensus Logic

    # --- MARKET CHECK TOOL ---
    if tool_name == "check_market_status":
        symbol = params.get("symbol", "UNKNOWN")
        status = market_service.check_status(symbol)
        return ToolResponse(status="SUCCESS", output=status)

    # --- SEMANTIC SAFETY TOOL ---
    elif tool_name == "verify_content_safety":
        text = params.get("text", "")

        # Use NeMo Guardrails for deep inspection (Jailbreak, PII, etc.)
        check_result = await nemo_manager.check_guardrails(text)

        # If NeMo blocked it (or if checking explicitly for blocking signal)
        if check_result.get("blocked", False):
             return ToolResponse(status="BLOCKED", error=f"NeMo Safety Violation: {check_result.get('response')}")

        # If response differs significantly and is short refusal, treat as block?
        # For now, we assume if it passed (blocked=False), it returns the (possibly masked) content.
        # But this tool expects "SAFE" as output if successful verification?
        # If the input was "Analyze AAPL", NeMo returns "Analyze AAPL".
        # If the input was PII, NeMo returns masked PII.

        return ToolResponse(status="SUCCESS", output=check_result.get("response"))

    # --- TRADE EXECUTION TOOL ---
    elif tool_name == "execute_trade":
        try:
            # Validate Schema
            try:
                order = TradeOrder(**params)
            except Exception as e:
                return ToolResponse(status="ERROR", error=f"Schema Validation Failed: {e}")

            # CBF Check
            cbf_result = safety_filter.verify_action(tool_name, params)
            if cbf_result.startswith("UNSAFE"):
                 return ToolResponse(status="BLOCKED", error=f"Safety Filter: {cbf_result}")

            # Consensus Check
            amount = params.get("amount", 0)
            symbol = params.get("symbol", "UNKNOWN")

            consensus = await consensus_engine.check_consensus(tool_name, amount, symbol)

            if consensus["status"] == "REJECT":
                 return ToolResponse(status="BLOCKED", error=f"Consensus Rejected: {consensus['reason']}")

            if consensus["status"] == "ESCALATE":
                 return ToolResponse(status="BLOCKED", error=f"Consensus Escalation: {consensus['reason']}")

            # DRY RUN CHECK
            is_dry_run = params.get("dry_run", False)
            if is_dry_run:
                logger.info(f"DRY RUN (System 3 Check): {tool_name} APPROVED by all gates.")
                return ToolResponse(status="SUCCESS", output="DRY_RUN: APPROVED by OPA, Safety, and Consensus.")

            # Update State
            safety_filter.update_state(amount)

            # 3. Execution
            result = await execute_trade(order)
            return ToolResponse(status="SUCCESS", output=result)

        except Exception as e:
            logger.error(f"Tool Execution Error: {e}")
            return ToolResponse(status="ERROR", error=str(e))

    else:
        return ToolResponse(status="ERROR", error=f"Unknown tool: {tool_name}")

@app.get("/health")
def health_check():
    return {"status": "ok"}

if __name__ == '__main__':
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
