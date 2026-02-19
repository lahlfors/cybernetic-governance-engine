import asyncio
import logging
from typing import Any, Callable, Dict, List

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from google.adk.tools import FunctionTool

logger = logging.getLogger("Infrastructure.MCPClient")

class GatewayMCPClient:
    """
    Client for interacting with the Gateway's MCP Server via SSE.
    """
    def __init__(self, sse_url: str):
        self.sse_url = sse_url
        self.session: ClientSession | None = None
        self._exit_stack = None

    async def connect(self):
        """Connects to the Gateway MCP SSE endpoint."""
        logger.info(f"Connecting to Gateway MCP at {self.sse_url}...")
        from contextlib import AsyncExitStack
        self._exit_stack = AsyncExitStack()

        # Connect via SSE
        read_stream, write_stream = await self._exit_stack.enter_async_context(
            sse_client(self.sse_url)
        )
        
        self.session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self.session.initialize()
        logger.info("✅ Connected to Gateway MCP.")

    async def list_tools(self) -> List[Any]:
        if not self.session:
            await self.connect()
        result = await self.session.list_tools()
        return result.tools

    async def call_tool(self, name: str, arguments: dict) -> Any:
        if not self.session:
            await self.connect()
        
        logger.info(f"📞 Calling MCP Tool: {name}")
        result = await self.session.call_tool(name, arguments)
        
        # Parse result (MCP returns a list of content objects)
        output = []
        if hasattr(result, 'content'):
            for content in result.content:
                if hasattr(content, 'text'):
                    output.append(content.text)
        
        return "\n".join(output)

    async def close(self):
        if self._exit_stack:
            await self._exit_stack.aclose()
            logger.info("MCP Client Closed.")

# Singleton Instance
_mcp_client_instance = None

def get_mcp_client() -> GatewayMCPClient:
    global _mcp_client_instance
    if not _mcp_client_instance:
        from config.settings import Config
        # Ensure Config has MCP_SERVER_SSE_URL
        url = getattr(Config, "MCP_SERVER_SSE_URL", "http://localhost:8080/mcp/sse")
        _mcp_client_instance = GatewayMCPClient(url)
    return _mcp_client_instance

def create_mcp_tool_adapter(tool_name: str, description: str = "") -> FunctionTool:
    """
    Creates a google.adk.tools.FunctionTool that proxies calls to the MCP Client.
    """
    client = get_mcp_client()
    
    async def _async_wrapper(**kwargs):
        return await client.call_tool(tool_name, kwargs)

    # Note: FunctionTool by default inspects signature.
    # Since **kwargs is generic, we rely on the Agent's prompt knowing the schema.
    # Ideally we'd synthesize a signature, but for ADK + LiteLLM, 
    # passing the definition manually in the Agent configuration is cleaner
    # if we want strict schema.
    # However, for this refactor, we assume the Agent knows what to call.
    
    # FunctionTool infers name/desc from the function itself
    _async_wrapper.__name__ = tool_name
    _async_wrapper.__doc__ = description
    
    return FunctionTool(_async_wrapper)

