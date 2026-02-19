import asyncio
import logging
import sys
import os

# Adjust path
sys.path.append(os.getcwd())

from src.governed_financial_advisor.agents.data_analyst.agent import create_data_analyst_executor
from google.adk.runners import Runner
from google.genai import types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestDataAnalyst")

async def test_data_analyst_execution():
    logger.info("--- Testing Data Analyst Agent (MCP Integration) ---")
    
    # Create Agent (Executor only for simplicity)
    agent = create_data_analyst_executor("AAPL")
    
    # Manually invoke tool to verify it uses MCP client
    # We can inspect the tool list
    mcp_tool = agent.tools[0]
    logger.info(f"Agent Tool: {mcp_tool.name} (Should be get_market_data via MCP adapter)")
    
    # We can try to run it.
    # Note: connect() might fail if Gateway is not up.
    try:
        logger.info("Invoking tool directly...")
        # Inspecting the wrapper locally
        if hasattr(mcp_tool, 'func'):
            # The wrapper is async
            res = await mcp_tool.func(ticker="AAPL")
            logger.info(f"✅ Tool Execution Result (Prefix): {str(res)[:100]}...")
        else:
            logger.warning(f"Tool does not have .func method. Dir: {dir(mcp_tool)}")
            
    except Exception as e:
        logger.error(f"❌ Tool Execution Failed: {e}")
        logger.error("Ensure Gateway is running: python src/gateway/server/hybrid_server.py")

if __name__ == "__main__":
    asyncio.run(test_data_analyst_execution())
