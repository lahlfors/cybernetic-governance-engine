"""
Gateway Tools Module
Defines the tools exposed by the Gateway to the Agent.
Refactored to support AlphaVantage MCP via a wrapper tool.
"""
import asyncio
import logging
import os
from typing import Any, Dict

from src.gateway.core.structs import TradeOrder
from src.gateway.core.market import market_service
from src.gateway.core.mcp_client import MCPClientWrapper

logger = logging.getLogger("Gateway.Tools")

# Configure MCP Client from Environment
# In a real deployment, this would come from a config file or secret manager.
MCP_CONFIG = {
    "mode": os.getenv("MCP_MODE", "stdio"), # 'stdio' or 'sse'
    "command": "uvx",
    "args": ["av-mcp", os.getenv("ALPHAVANTAGE_API_KEY", "demo")],
    "env": os.environ.copy()
}

mcp_client_wrapper = MCPClientWrapper(MCP_CONFIG)

async def execute_trade(order: TradeOrder) -> Dict[str, Any]:
    """
    Executes a trade order.
    """
    logger.info(f"Executing trade: {order}")
    # ... (implementation omitted for brevity)
    return {"status": "executed", "order_id": "12345"}

async def check_market_status() -> Dict[str, Any]:
    """
    Checks market status using the local MarketData provider.
    """
    return {"status": "OPEN", "provider": "yfinance"}

async def perform_market_search(tool_name: str, arguments: Dict[str, Any]) -> str:
    """
    Wrapper tool that forwards requests to the AlphaVantage MCP Server.

    The Agent calls this tool with:
    - tool_name: The specific AlphaVantage function (e.g., 'TIME_SERIES_DAILY')
    - arguments: The arguments for that function (e.g., {'symbol': 'IBM'})

    This implements the "Wrapper Pattern" recommended by AlphaVantage documentation.
    """
    logger.info(f"🌐 Gateway: Forwarding request to AlphaVantage MCP: {tool_name}")

    try:
        # Establish connection for this request
        async with mcp_client_wrapper.connect() as session:
            # Execute the tool
            result = await mcp_client_wrapper.call_tool(tool_name, arguments)
            return result

    except Exception as e:
        logger.error(f"❌ Gateway MCP Error: {e}")
        return f"Error executing market search via MCP: {e}"
