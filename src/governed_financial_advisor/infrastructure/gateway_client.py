"""
Gateway Client Wrapper (HTTP/REST)
Replaces gRPC Client with HTTP/REST Client.
"""
import logging
import os
import json
import httpx
from typing import Any, Optional, Dict

logger = logging.getLogger("GatewayClient")

class GatewayClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.client = None
            cls._instance.base_url = None
        return cls._instance

    async def close(self):
        """Closes the HTTP session."""
        if self.client:
            await self.client.aclose()
            logger.info("GatewayClient HTTP session closed.")

    def _ensure_connection(self):
        """
        Ensures the HTTP client exists.
        """
        if self.client is None or self.client.is_closed:
            host = os.getenv("GATEWAY_HOST", "localhost")
            port = os.getenv("PORT", "8080") # Default HTTP Port

            # Construct Base URL
            if not host.startswith("http"):
                self.base_url = f"http://{host}:{port}"
            else:
                # Assuming host includes scheme, append port if not present?
                # Usually GATEWAY_HOST might be just host.
                # Let's assume standard format.
                if ":" not in host.split("//")[-1]:
                     self.base_url = f"{host}:{port}"
                else:
                     self.base_url = host
            
            logger.info(f"Connecting to Gateway (HTTP) at {self.base_url}...")
            # Use a reasonable timeout for LLM/Tool calls
            self.client = httpx.AsyncClient(base_url=self.base_url, timeout=120.0)

    def connect(self, host=None, port=None):
        # Deprecated: alias to _ensure_connection
        self._ensure_connection()

    async def execute_tool(self, tool_name: str, params: dict) -> str:
        """
        Calls ExecuteTool via HTTP POST /tools/execute.
        """
        self._ensure_connection()

        try:
            response = await self.client.post("/tools/execute", json={
                "tool_name": tool_name,
                "params": params
            })

            # We don't raise immediately because 4xx might be a governance block we want to parse
            if response.status_code >= 500:
                response.raise_for_status()

            result = response.json()

            if result.get("status") == "SUCCESS":
                return result.get("output")
            elif result.get("status") == "BLOCKED":
                 return f"BLOCKED: {result.get('error')}"
            else:
                 return f"ERROR: {result.get('error', 'Unknown Error')}"

        except Exception as e:
            logger.error(f"HTTP Tool Execution Failed: {e}")
            return f"SYSTEM ERROR: {e}"

    async def chat(self, prompt: str, system_instruction: str | None = None, mode: str = "chat", **kwargs) -> str:
        """
        Invokes LLM via HTTP POST /v1/chat/completions.
        """
        self._ensure_connection()

        # Build Message List
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        # Build Request Payload
        payload = {
            "model": kwargs.get("model", "default"),
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.0),
            "stream": False, # Enforce non-streaming for now as per method signature returning str
            "guided_json": kwargs.get("guided_json"),
            "guided_regex": kwargs.get("guided_regex"),
            "guided_choice": kwargs.get("guided_choice")
        }

        try:
            response = await self.client.post("/v1/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error(f"HTTP Chat Failed: {e}")
            raise e

# Singleton instance
gateway_client = GatewayClient()
