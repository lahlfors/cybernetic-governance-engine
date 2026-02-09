import asyncio
import os
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.types import CallToolResult, EmbeddedResource, ImageContent, TextContent

logger = logging.getLogger("Gateway.MCPClient")

class MCPClientWrapper:
    """
    A wrapper around the MCP ClientSession to handle connection management
    and tool execution for AlphaVantage.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.session: Optional[ClientSession] = None

    @asynccontextmanager
    async def connect(self):
        """
        Establishes a connection to the MCP server.
        Supports 'stdio' (local) and 'sse' (remote) modes.
        """
        mode = self.config.get("mode", "stdio")

        try:
            if mode == "stdio":
                # Local execution (e.g. via uvx)
                command = self.config.get("command", "uvx")
                args = self.config.get("args", [])
                env = self.config.get("env", None)
                if env is None:
                    env = os.environ.copy()

                logger.info(f"🔌 Connecting to MCP (STDIO): {command} {args}")

                server_params = StdioServerParameters(
                    command=command,
                    args=args,
                    env=env
                )

                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        self.session = session
                        logger.info("✅ MCP Session Initialized (STDIO)")
                        yield session

            elif mode == "sse":
                # Remote execution (HTTP SSE)
                url = self.config.get("url")
                headers = self.config.get("headers", {})

                logger.info(f"🔌 Connecting to MCP (SSE): {url}")

                async with sse_client(url=url, headers=headers) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        self.session = session
                        logger.info("✅ MCP Session Initialized (SSE)")
                        yield session
            else:
                raise ValueError(f"Unsupported MCP mode: {mode}")

        except Exception as e:
            logger.error(f"❌ MCP Connection Failed: {e}")
            raise
        finally:
            self.session = None

    async def list_tools(self) -> Any:
        """Lists available tools from the MCP server."""
        if not self.session:
            raise RuntimeError("MCP Session not active")
        return await self.session.list_tools()

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> str:
        """
        Calls a tool on the MCP server.
        Handles text, image, and resource content.
        """
        if not self.session:
            raise RuntimeError("MCP Session not active")

        logger.info(f"🛠️ MCP Tool Call: {tool_name} args={arguments}")

        result: CallToolResult = await self.session.call_tool(tool_name, arguments or {})

        output_text = []
        if result.isError:
            msg = f"MCP Tool Error: {result.content}"
            logger.error(msg)
            return msg

        for content in result.content:
            if isinstance(content, TextContent):
                output_text.append(content.text)
            elif isinstance(content, ImageContent):
                output_text.append(f"[Image: {content.mimeType}]")
            elif isinstance(content, EmbeddedResource):
                output_text.append(f"[Resource: {content.resource.uri}]")
            # Fallback for other/unknown types if necessary
            elif hasattr(content, 'text'):
                output_text.append(content.text)

        return "\n".join(output_text)
