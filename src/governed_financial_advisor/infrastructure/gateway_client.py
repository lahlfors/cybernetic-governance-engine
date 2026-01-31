"""
Gateway Client Wrapper (Async)
"""
import grpc.aio
import json
import logging
import os
import google.auth
from google.auth.transport.requests import Request as AuthRequest
from google.oauth2 import id_token

from src.gateway.protos import gateway_pb2
from src.gateway.protos import gateway_pb2_grpc

logger = logging.getLogger("GatewayClient")

class GatewayClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GatewayClient, cls).__new__(cls)
            cls._instance.channel = None
            cls._instance.stub = None
            cls._instance.target_url = None
        return cls._instance

    def _get_auth_metadata(self):
        """
        Fetches OIDC Token for Cloud Run Service-to-Service authentication.
        Only runs if target_url is set (implies remote Cloud Run).
        """
        if not self.target_url or "localhost" in self.target_url:
            return None

        try:
            # Clean URL for audience (remove protocol)
            audience = self.target_url.replace("https://", "").replace("http://", "")
            # Actually, id_token.fetch_id_token expects the full URL as audience usually?
            # Cloud Run audience is the Service URL.

            # Use google.auth to check connectivity/creds
            auth_req = AuthRequest()
            token = id_token.fetch_id_token(auth_req, self.target_url)
            return (("authorization", f"Bearer {token}"),)
        except Exception as e:
            logger.warning(f"Failed to fetch OIDC token for Gateway: {e}")
            return None

    def connect(self, host=None, port=None):
        if not host:
            host = os.getenv("GATEWAY_HOST", "localhost")
        if not port:
            port = os.getenv("GATEWAY_PORT", "50051")

        if not self.channel:
            # Detect if running on Cloud Run (using HTTPS usually)
            if host != "localhost":
                # Assume secure channel for Cloud Run
                # Cloud Run URLs are https://... so host might contain protocol
                if "https://" in host:
                    target = host.replace("https://", "")
                    creds = grpc.ssl_channel_credentials()
                    self.channel = grpc.aio.secure_channel(target, creds)
                    self.target_url = host
                else:
                    # Fallback or internal IP
                    target = f"{host}:{port}"
                    self.channel = grpc.aio.insecure_channel(target)
                    self.target_url = None # Assume no auth needed for plain IP/localhost
            else:
                target = f"{host}:{port}"
                self.channel = grpc.aio.insecure_channel(target)
                self.target_url = None

            self.stub = gateway_pb2_grpc.GatewayStub(self.channel)
            logger.info(f"Connected to Gateway at {target} (Auth: {self.target_url is not None})")

    async def execute_tool(self, tool_name: str, params: dict) -> str:
        if not self.stub:
            self.connect()

        metadata = self._get_auth_metadata()

        req = gateway_pb2.ToolRequest(
            tool_name=tool_name,
            params_json=json.dumps(params)
        )

        try:
            resp = await self.stub.ExecuteTool(req, metadata=metadata)
            if resp.status == "SUCCESS":
                return resp.output
            else:
                return f"BLOCKED/ERROR: {resp.error}"
        except grpc.aio.AioRpcError as e:
            logger.error(f"RPC Failed: {e}")
            return f"SYSTEM ERROR: Could not reach Gateway. {e.details()}"

    async def chat(self, prompt: str, system_instruction: str = None, mode: str = "chat", **kwargs) -> str:
        if not self.stub:
            self.connect()

        metadata = self._get_auth_metadata()

        msgs = []
        msgs.append(gateway_pb2.Message(role="user", content=prompt))

        temperature = kwargs.get("temperature", 0.0)
        guided_json = None
        if "guided_json" in kwargs:
             guided_json = json.dumps(kwargs["guided_json"])

        req = gateway_pb2.ChatRequest(
            model="default",
            messages=msgs,
            temperature=temperature,
            system_instruction=system_instruction,
            mode=mode,
            guided_json=guided_json,
            guided_regex=kwargs.get("guided_regex"),
            guided_choice=str(kwargs.get("guided_choice")) if kwargs.get("guided_choice") else None
        )

        full_text = []
        try:
            call = self.stub.Chat(req, metadata=metadata)
            async for resp in call:
                full_text.append(resp.content)

            return "".join(full_text)
        except grpc.aio.AioRpcError as e:
            logger.error(f"Chat RPC Failed: {e}")
            raise e

# Singleton instance
gateway_client = GatewayClient()
