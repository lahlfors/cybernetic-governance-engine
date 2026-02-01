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
        if not self.target_url or "localhost" in self.target_url or "127.0.0.1" in self.target_url:
            return None

        try:
            # Use google.auth to check connectivity/creds
            # When calling Cloud Run, the audience is the Service URL
            auth_req = AuthRequest()
            # Verify if target_url has protocol, if not add https:// for audience generation if needed,
            # but usually fetch_id_token expects the exact audience string of the service.
            audience = self.target_url
            if not audience.startswith("http"):
                audience = f"https://{audience}"

            token = id_token.fetch_id_token(auth_req, audience)
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
            if host != "localhost" and host != "127.0.0.1":
                # Assume secure channel for Cloud Run if port is 443 or https protocol specified
                if "https://" in host or port == "443":
                    target = host.replace("https://", "")
                    # Strip port if 443 to avoid SNI issues if needed, or keep it.
                    # GRPC secure channel usually wants host:port or just host.
                    if ":443" in target:
                        target = target # keep as is

                    creds = grpc.ssl_channel_credentials()
                    self.channel = grpc.aio.secure_channel(target, creds)
                    self.target_url = host # Set full URL for Audience derivation
                else:
                    # Fallback or internal IP (e.g. PSC IP)
                    target = f"{host}:{port}"
                    self.channel = grpc.aio.insecure_channel(target)
                    # If using PSC with IP, we might still need Auth if the service requires it.
                    # But usually PSC endpoints are accessed via HTTP/2 cleartext (h2c) inside VPC?
                    # Let's assume if it's not localhost, we might need auth unless configured otherwise.
                    # For now, treat non-https as insecure/no-auth unless overridden.
                    self.target_url = None
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
