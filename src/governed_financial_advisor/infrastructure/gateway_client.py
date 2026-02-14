"""
Gateway Client Wrapper (HTTP/MCP)
Replaces gRPC Client with standard HTTPX client for MCP/REST.
"""
import logging
import os
import json
import httpx
from typing import AsyncGenerator, Optional, Any

logger = logging.getLogger("GatewayClient")

class GatewayClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.client = None
            cls._instance.base_url = None
        return cls._instance

    def _ensure_client(self):
        """
        Ensures the HTTP client exists.
        """
        if self.client is None:
            host = os.getenv("GATEWAY_HOST", "localhost")
            port = os.getenv("GATEWAY_PORT", "8080")
            # Determine protocol (http vs https)
            protocol = "http"
            if "https" in host: # simple heuristic
                protocol = "https"
            
            # Construct base URL
            # If host already has protocol, use it
            if "://" in host:
                self.base_url = f"{host}:{port}"
            else:
                self.base_url = f"{protocol}://{host}:{port}"

            logger.info(f"Initializing Gateway Client (HTTP) at {self.base_url}...")
            # Use distinct client for long-lived connection pooling
            self.client = httpx.AsyncClient(base_url=self.base_url, timeout=60.0)

    async def close(self):
        """Closes the HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None
            logger.info("GatewayClient HTTP connection closed.")

    async def execute_tool(self, tool_name: str, params: dict) -> str:
        """
        Calls ExecuteTool via HTTP POST /tools/execute.
        """
        self._ensure_client()

        try:
            payload = {
                "tool_name": tool_name,
                "params": params
            }

            response = await self.client.post("/tools/execute", json=payload)
            response.raise_for_status()

            data = response.json()
            if data.get("status") == "SUCCESS":
                return data.get("output")
            else:
                return f"BLOCKED: {data.get('error') or data.get('output')}"

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Tool Execution Failed: {e.response.text}")
            return f"SYSTEM ERROR: {e.response.status_code} {e.response.text}"
        except Exception as e:
            logger.error(f"Tool Execution Error: {e}")
            return f"SYSTEM ERROR: {str(e)}"

    async def chat(self, prompt: str, system_instruction: str | None = None, mode: str = "chat", **kwargs) -> str:
        """
        Invokes LLM via HTTP Chat Endpoint (/v1/chat/completions).
        Currently supports non-streaming.
        """
        self._ensure_client()

        # Build Messages
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        # Prepare Payload
        payload = {
            "model": kwargs.get("model", "default"),
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.0),
            "stream": False, # TODO: Support streaming via SSE/Line iteration
            "system_instruction": system_instruction,
            "guided_json": kwargs.get("guided_json"),
            "guided_regex": kwargs.get("guided_regex"),
            "guided_choice": kwargs.get("guided_choice")
        }

        try:
            response = await self.client.post("/v1/chat/completions", json=payload)
            response.raise_for_status()

            data = response.json()
            # OpenAI Format
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]
            else:
                return ""

        except Exception as e:
            logger.error(f"HTTP Chat Failed: {e}")
            raise e

# Singleton instance
gateway_client = GatewayClient()
