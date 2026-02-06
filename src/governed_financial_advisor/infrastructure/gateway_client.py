"""
Gateway Client Wrapper (HTTP/REST)
Refactored to use httpx instead of gRPC.
"""
import json
import logging
import os
import httpx
from typing import Optional, Any, Dict, List

import google.auth
from google.auth.transport.requests import Request as AuthRequest
from google.oauth2 import id_token

logger = logging.getLogger("GatewayClient")

class GatewayClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GatewayClient, cls).__new__(cls)
            cls._instance.client: Optional[httpx.AsyncClient] = None
            cls._instance.base_url: Optional[str] = None
        return cls._instance

    def _get_auth_token(self) -> Optional[str]:
        """
        Fetches OIDC Token for Cloud Run Service-to-Service authentication.
        """
        if not self.base_url or "localhost" in self.base_url or "127.0.0.1" in self.base_url:
            return None

        try:
            auth_req = AuthRequest()
            audience = self.base_url
            if not audience.startswith("http"):
                audience = f"https://{audience}"

            # Use the base URL (service root) as audience usually
            # If base_url has path, strip it? Cloud Run audience is usually the base URL.
            token = id_token.fetch_id_token(auth_req, audience)
            return token
        except Exception as e:
            logger.debug(f"Could not fetch OIDC token (might be local or no creds): {e}")
            return None

    def connect(self, host=None, port=None):
        """
        Initializes the HTTP client.
        """
        if not host:
            host = os.getenv("GATEWAY_HOST", "localhost")
        if not port:
            port = os.getenv("GATEWAY_PORT", "8080")

        if not self.client:
            if host.startswith("http"):
                self.base_url = host
            elif "localhost" in host or "127.0.0.1" in host:
                self.base_url = f"http://{host}:{port}"
            else:
                 # Assume HTTPS for remote
                self.base_url = f"https://{host}"

            logger.info(f"Gateway Client connecting to: {self.base_url}")

            # Configure timeouts (LLM calls can be long)
            self.client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=120.0
            )

    async def execute_tool(self, tool_name: str, params: dict) -> str:
        if not self.client:
            self.connect()

        headers = {}
        token = self._get_auth_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        payload = {
            "tool_name": tool_name,
            "params": params
        }

        try:
            response = await self.client.post("/tools/execute", json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()
            if data["status"] == "SUCCESS":
                return data["output"]
            else:
                return f"BLOCKED/ERROR: {data.get('error', 'Unknown Error')}"

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Error executing tool: {e.response.text}")
            return f"SYSTEM ERROR: Gateway returned {e.response.status_code}"
        except httpx.RequestError as e:
            logger.error(f"Request Error executing tool: {e}")
            return f"SYSTEM ERROR: Could not reach Gateway. {e}"

    async def chat(self, prompt: str, system_instruction: str = None, mode: str = "chat", **kwargs) -> str:
        if not self.client:
            self.connect()

        headers = {}
        token = self._get_auth_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "model": "default",
            "temperature": kwargs.get("temperature", 0.0),
            "system_instruction": system_instruction,
            "mode": mode,
            # Pass guided_json as dict directly
            "guided_json": kwargs.get("guided_json"),
            "guided_regex": kwargs.get("guided_regex"),
            "guided_choice": kwargs.get("guided_choice")
        }

        try:
            response = await self.client.post("/chat", json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()
            return data["content"]

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Error in chat: {e.response.text}")
            raise RuntimeError(f"Gateway Chat Error: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Request Error in chat: {e}")
            raise RuntimeError(f"Gateway Connection Error: {e}")

    async def close(self):
        if self.client:
            await self.client.aclose()
            self.client = None

# Singleton instance
gateway_client = GatewayClient()
