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
            cls._instance._base_url = None
        return cls._instance

    def _get_base_url(self) -> str:
        """Constructs the base URL if not already cached."""
        if self._base_url:
            return self._base_url
            
        host = os.getenv("GATEWAY_HOST", "localhost")
        port = os.getenv("GATEWAY_PORT", "8080")
        
        # Determine protocol (http vs https)
        protocol = "http"
        if "https" in host: # simple heuristic
            protocol = "https"
        
        # Construct base URL
        # If host already has protocol, use it
        if "://" in host:
            base_url = f"{host}:{port}"
        else:
            base_url = f"{protocol}://{host}:{port}"
            
        logger.info(f"Gateway URL: {base_url}")
        self._base_url = base_url
        return base_url

    async def execute_tool(self, tool_name: str, params: dict) -> str:
        """
        Calls ExecuteTool via HTTP POST /tools/execute.
        Uses a fresh client per request to avoid asyncio loop mismatch.
        """
        base_url = self._get_base_url()

        try:
            async with httpx.AsyncClient(base_url=base_url, timeout=60.0) as client:
                payload = {
                    "tool_name": tool_name,
                    "params": params
                }

                response = await client.post("/tools/execute", json=payload)
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
        base_url = self._get_base_url()

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
            async with httpx.AsyncClient(base_url=base_url, timeout=120.0) as client:
                response = await client.post("/v1/chat/completions", json=payload)
                response.raise_for_status()

                data = response.json()
                # OpenAI Format
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"]
                elif "content" in data: # Fallback
                     return data["content"]
                else:
                    return ""

        except Exception as e:
            logger.error(f"HTTP Chat Failed: {e}")
            raise e

# Singleton instance
gateway_client = GatewayClient()
