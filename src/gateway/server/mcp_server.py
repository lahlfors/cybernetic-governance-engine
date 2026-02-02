import asyncio
import logging
import json
import os
import sys

# Adjust path so we can import from src
sys.path.append(".")

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

# Reuse existing core logic
from src.gateway.core.policy import OPAClient
from src.gateway.core.tools import execute_trade, TradeOrder
from src.gateway.core.market import market_service
from src.governed_financial_advisor.governance.consensus import consensus_engine
from src.governed_financial_advisor.governance.safety import safety_filter

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Gateway.MCP")

# Initialize FastMCP Server
mcp = FastMCP("Governed Financial Advisor Gateway")

# Initialize Governance Clients
opa_client = OPAClient()

# --- HELPER: Governance Decorator Logic ---
async def enforce_governance(tool_name: str, params: dict):
    """
    Centralized Governance Check (OPA, Safety, Consensus).
    Raises Exception if blocked.
    """
    # 1. OPA Check
    if tool_name not in ["check_market_status", "verify_content_safety"]:
        payload = params.copy()
        payload['action'] = tool_name
        # Check for dry_run
        decision = await opa_client.evaluate_policy(payload)

        if decision == "DENY":
            raise PermissionError(f"OPA Policy Violation: Action '{tool_name}' DENIED.")
        if decision == "MANUAL_REVIEW":
            logger.critical(f"MANUAL REVIEW REQUIRED for {tool_name}")
            raise PermissionError("Manual Review Triggered - Admin Notified.")

    # 2. Safety Filter (CBF)
    # Only applicable for trade execution currently
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

# --- MCP TOOLS ---

@mcp.tool()
async def check_market_status(symbol: str) -> str:
    """
    Checks the current market status and price for a given ticker symbol.
    """
    # Low-risk tool, minimal governance (logging only)
    logger.info(f"Tool Call: check_market_status({symbol})")
    return market_service.check_status(symbol)

@mcp.tool()
async def verify_content_safety(text: str) -> str:
    """
    Verifies if the provided text content is safe (Jailbreak detection).
    Returns 'SAFE' or error message.
    """
    logger.info("Tool Call: verify_content_safety")
    if "jailbreak" in text.lower() or "ignore previous" in text.lower():
         return "BLOCKED: Semantic Safety Violation (Jailbreak Pattern)"
    return "SAFE"

@mcp.tool()
async def execute_trade_action(symbol: str, amount: float, currency: str, transaction_id: str = None, trader_id: str = "agent_001", trader_role: str = "junior", dry_run: bool = False) -> str:
    """
    Executes a financial trade under strict governance.
    """
    logger.info(f"Tool Call: execute_trade({symbol}, {amount})")

    # Construct Params for Governance
    # If transaction_id is missing, pydantic model in core/tools will generate it, but we need it for logging?
    # Actually, let's let the TradeOrder model handle defaults if None
    import uuid
    if not transaction_id:
        transaction_id = str(uuid.uuid4())

    params = {
        "symbol": symbol,
        "amount": amount,
        "currency": currency,
        "transaction_id": transaction_id,
        "trader_id": trader_id,
        "trader_role": trader_role,
        "dry_run": dry_run
    }

    # 1. Enforce Governance
    try:
        await enforce_governance("execute_trade", params)
    except Exception as e:
        return f"BLOCKED: {e}"

    if dry_run:
        return "DRY_RUN: APPROVED by OPA, Safety, and Consensus."

    # 2. Update State
    safety_filter.update_state(amount)

    # 3. Execute
    try:
        # Validate with Pydantic
        order = TradeOrder(**params)
        result = await execute_trade(order)
        return result
    except Exception as e:
        logger.error(f"Execution Error: {e}")
        return f"ERROR: {e}"

# --- RUNNER ---
if __name__ == "__main__":
    # In Docker/Production, we use SSE on port 50051 (replacing gRPC)
    port = int(os.getenv("PORT", 50051))
    print(f"🚀 MCP Gateway Server starting on port {port} (SSE)...")

    # FastMCP run method handles uvicorn startup
    mcp.run(transport="sse", port=port)
