import asyncio
import logging
import os
import sys
import requests

# Adjust path to find src
sys.path.append(os.getcwd())

from src.governed_financial_advisor.infrastructure.mcp_client import GatewayMCPClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestGateway")

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8080")
MCP_SSE_URL = f"{GATEWAY_URL}/mcp/sse"

async def test_mcp_connection():
    logger.info("--- Testing MCP Connection ---")
    client = GatewayMCPClient(MCP_SSE_URL)
    try:
        await client.connect()
        tools = await client.list_tools()
        logger.info(f"✅ MCP Connected. Found {len(tools)} tools.")
        for tool in tools:
            logger.info(f"   - {tool.name}")
            
        # Optional: Call a simple tool if exists
        # result = await client.call_tool("check_market_status", {"symbol": "AAPL"})
        # logger.info(f"Tool Result: {result}")
        
    except Exception as e:
        logger.error(f"❌ MCP Connection Failed: {e}")
    finally:
        await client.close()

def test_chat_proxy():
    logger.info("\n--- Testing Chat Proxy (HTTP) ---")
    url = f"{GATEWAY_URL}/v1/chat/completions"
    payload = {
        "model": "default",
        "messages": [{"role": "user", "content": "Hello, are you online?"}],
        "stream": False
    }
    
    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            logger.info(f"✅ Chat Proxy working. Response: {res.json()}")
        else:
            logger.error(f"❌ Chat Proxy Failed: {res.status_code} - {res.text}")
            
    except Exception as e:
         logger.error(f"❌ Chat Proxy Connection Error: {e}")

if __name__ == "__main__":
    test_chat_proxy()
    asyncio.run(test_mcp_connection())
