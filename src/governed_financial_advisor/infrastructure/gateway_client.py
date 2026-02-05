"""
Gateway Client Wrapper (Hybrid: MCP + REST)
Uses mcp.client.sse for Tools and httpx for Chat.
"""
import logging
import os
import json
import asyncio
import httpx
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
            cls._instance.sse_url = None
            cls._instance.chat_url = None
            cls._instance.client = None
        return cls._instance

    def connect(self, host=None, port=None):
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=120.0)

        if not host:
            host = os.getenv("GATEWAY_HOST", "localhost")
        if not port:
            port = os.getenv("GATEWAY_PORT", "8080")

        # Build Base URL
        protocol = "http"
        if "https" in host:
            protocol = "https"
            host = host.replace("https://", "")

        base_url = f"{protocol}://{host}:{port}"
        self.sse_url = f"{base_url}/mcp/sse"
        self.chat_url = f"{base_url}/v1/chat/completions"
        logger.info(f"Configured Gateway Client: SSE={self.sse_url}, Chat={self.chat_url}")

    async def execute_tool(self, tool_name: str, params: dict) -> str:
        """
        Calls an MCP Tool on the Gateway Server.
        """
        if not self.sse_url:
            self.connect()

        try:
            # MCP Client Session Context Manager
            async with sse_client(self.sse_url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    # Map 'execute_trade' -> 'execute_trade_action' if needed
                    target_tool = tool_name
                    if tool_name == "execute_trade":
                        target_tool = "execute_trade_action"

                    # Call Tool
                    result = await session.call_tool(target_tool, arguments=params)

                    output_text = []
                    for content in result.content:
                        if content.type == "text":
                            output_text.append(content.text)

                    full_output = "\n".join(output_text)

                    if full_output.startswith("BLOCKED") or full_output.startswith("ERROR"):
                         return f"{full_output}"

                    return full_output

        except Exception as e:
            logger.error(f"MCP Tool Call Failed: {e}")
            return f"SYSTEM ERROR: Could not call MCP Gateway. {e}"

    async def chat(self, prompt: str, system_instruction: str = None, mode: str = "chat", **kwargs) -> str:
        """
        Invokes LLM via Gateway REST Endpoint.
        """
        if not self.chat_url:
            self.connect()

        payload = {
            "model": kwargs.get("model", "default"),
            "messages": [],
            "temperature": kwargs.get("temperature", 0.0),
            "stream": False
        }

        if system_instruction:
            payload["messages"].append({"role": "system", "content": system_instruction})
        payload["messages"].append({"role": "user", "content": prompt})

        # Forward guided generation params
        if "guided_json" in kwargs: payload["guided_json"] = kwargs["guided_json"]
        if "guided_regex" in kwargs: payload["guided_regex"] = kwargs["guided_regex"]
        if "guided_choice" in kwargs: payload["guided_choice"] = kwargs["guided_choice"]

        try:
            # Use persistent client
            if self.client is None:
                self.client = httpx.AsyncClient(timeout=120.0)

            resp = await self.client.post(self.chat_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            # OpenAI format: choices[0].message.content
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Chat Request Failed: {e}")
            raise e

    async def close(self):
        """Closes the underlying HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None

# Singleton instance
gateway_client = GatewayClient()
