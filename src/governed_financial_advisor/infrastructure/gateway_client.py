"""
Gateway Client Wrapper (MCP Implementation)
Uses mcp.client.sse to connect to the Gateway MCP Server.
"""
import logging
import os
import json
import asyncio
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.types import CallToolRequest, Tool

logger = logging.getLogger("GatewayClient")

class GatewayClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GatewayClient, cls).__new__(cls)
            cls._instance.url = None
        return cls._instance

    def connect(self, host=None, port=None):
        if not host:
            host = os.getenv("GATEWAY_HOST", "localhost")
        if not port:
            port = os.getenv("GATEWAY_PORT", "50051")

        # Build SSE URL
        protocol = "http"
        if "https" in host:
            protocol = "https"
            host = host.replace("https://", "")

        self.url = f"{protocol}://{host}:{port}/sse"
        logger.info(f"Configured MCP Gateway Client for: {self.url}")

    async def execute_tool(self, tool_name: str, params: dict) -> str:
        """
        Calls an MCP Tool on the Gateway Server.
        """
        if not self.url:
            self.connect()

        try:
            # MCP Client Session Context Manager
            # Note: For high frequency, we might want to keep the session open,
            # but SSE connections can be fragile. Retrying per-request is safer for now.
            async with sse_client(self.url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    # Map 'execute_trade' -> 'execute_trade_action' if needed, or update server to match.
                    # Server has `execute_trade_action`.
                    target_tool = tool_name
                    if tool_name == "execute_trade":
                        target_tool = "execute_trade_action"

                    # Call Tool
                    result = await session.call_tool(target_tool, arguments=params)

                    # Result is a CallToolResult with content list
                    # usually [TextContent(type='text', text='...')]
                    output_text = []
                    for content in result.content:
                        if content.type == "text":
                            output_text.append(content.text)

                    full_output = "\n".join(output_text)

                    # Check for "BLOCKED" or "ERROR" prefix conventions used in our server
                    if full_output.startswith("BLOCKED") or full_output.startswith("ERROR"):
                         return f"{full_output}"

                    return full_output

        except Exception as e:
            logger.error(f"MCP Tool Call Failed: {e}")
            return f"SYSTEM ERROR: Could not call MCP Gateway. {e}"

    async def chat(self, prompt: str, system_instruction: str = None, mode: str = "chat", **kwargs) -> str:
        """
        Deprecated: MCP Gateway is primarily for TOOLS.
        Chat logic should now be handled by the Agent invoking the LLM directly,
        OR via a specialized "chat" tool if we exposed one.

        For refactor compatibility, we will assume the Gateway Server
        might expose a 'chat' tool or we throw NotImplementedError
        forcing the Agent to use its own LLM Client (Open Weights).
        """
        raise NotImplementedError(
            "Gateway.chat() is deprecated in MCP Refactor. "
            "Agents should use their local HybridClient/OpenAI Client directly."
        )

# Singleton instance
gateway_client = GatewayClient()
