import logging
import json
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.governed_financial_advisor.tools.market_data_tool import get_market_data
from src.governed_financial_advisor.tools.trades import execute_trade, propose_trade
from src.gateway.governance.singletons import symbolic_governor, opa_client
from src.gateway.governance.nemo.manager import validate_with_nemo, load_rails

logger = logging.getLogger("ToolsRouter")

tools_router = APIRouter(prefix="/tools", tags=["tools"])

# Initialize Rails (Lazy load or use singleton if possible)
# In server.py, rails is initialized. We can try to import it or re-initialize.
# Re-initializing might be expensive. Best to share.
# For now, we'll load it here too or rely on caching.
_rails = None

def get_rails():
    global _rails
    if _rails is None:
        _rails = load_rails()
    return _rails

class ToolExecutionRequest(BaseModel):
    tool_name: str
    params: Dict[str, Any]

@tools_router.post("/execute")
async def execute_tool_endpoint(request: ToolExecutionRequest):
    """
    Executes a named tool directly via HTTP.
    Matches the checks performed by GatewayClient.
    """
    logger.info(f"Tool Execution Request: {request.tool_name}")
    
    try:
        output = None
        tool = request.tool_name
        params = request.params

        # --- Dispatcher ---
        
        if tool == "check_market_status":
            symbol = params.get("symbol")
            if not symbol:
                raise ValueError("Missing 'symbol' parameter")
            output = get_market_data(symbol)

        elif tool == "get_market_sentiment":
            # Reuse get_market_data for now as it includes news
            symbol = params.get("symbol")
            output = get_market_data(symbol) # Fallback to same tool

        elif tool == "check_safety_constraints":
            target_tool = params.get("target_tool")
            target_params = params.get("target_params") or {}
            risk = params.get("risk_profile", "Medium")
            # Call Symbolic Governor
            violations = await symbolic_governor.verify(target_tool, target_params)
            if not violations:
                output = "APPROVED: No violations detected."
            else:
                output = f"REJECTED: {'; '.join(violations)}"

        elif tool == "trigger_safety_intervention":
            reason = params.get("reason", "Unknown")
            from src.governed_financial_advisor.infrastructure.redis_client import redis_client
            redis_client.set("safety_violation", reason)
            output = "INTERVENTION_ACK: System Locked."

        elif tool == "verify_content_safety":
            text = params.get("text", "")
            is_safe, response = await validate_with_nemo(text, get_rails())
            if not is_safe:
                output = f"BLOCKED: {response}"
            else:
                output = "SAFE"

        elif tool == "evaluate_policy":
            # Map params to OPA inputs
            # OPAClient.evaluate_policy expects dictionary with 'action' etc.
            # params might contain 'action' already.
            # verify_policy_opa wrapper passed 'action' in params.
            decision = await opa_client.evaluate_policy(params)
            if decision == "ALLOW": output = "APPROVED: Action matches policy."
            elif decision == "DENY": output = "DENIED: Policy Violation."
            elif decision == "MANUAL_REVIEW": output = "MANUAL_REVIEW: Requires human approval."
            else: output = f"UNKNOWN: {decision}"

        elif tool == "execute_trade":
            # Use the local trade execution logic which calls Gateway?
            # Wait, execute_trade in tools/trades.py CALLS GATEWAY_CLIENT.
            # If we call it here, we create a loop if this IS the gateway.
            # We must use the INTERNAL implementation if we are the gateway.
            # But the Agent calls `execute_trade` tool.
            # If `governed_financial_advisor` IS the execution engine, it should execute it.
            # We don't have a separate "Execution Engine".
            # We should call `src.gateway.core.tools.execute_trade` (from imports in hybrid_server)?
            
            # Let's import the core trade logic
            from src.gateway.core.tools import execute_trade as core_execute_trade
            from src.gateway.core.structs import TradeOrder
            
            # Reconstruct TradeOrder
            # Params comes as dict
            # We might need to handle transaction_id generation if missing
            import uuid
            if "transaction_id" not in params:
                params["transaction_id"] = str(uuid.uuid4())
                
            order = TradeOrder(**params)
            # Enforce Governance Checks via SymbolicGovernor?
            # Gateway usually does:
            # await symbolic_governor.govern("execute_trade", params)
            # Then executes.
            
            await symbolic_governor.govern("execute_trade", params)
            output = await core_execute_trade(order)

        else:
            raise HTTPException(status_code=404, detail=f"Tool '{tool}' not found")

        return {"status": "SUCCESS", "output": str(output)}

    except Exception as e:
        logger.error(f"Tool Execution Error: {e}")
        # Return structured error so GatewayClient can parse it
        return {"status": "ERROR", "error": str(e)}
