"""
Gateway Client Wrapper (gRPC)
Replaces Hybrid/REST Client with efficient gRPC stubs.
"""
import logging
import os
import json
import asyncio
import grpc
from typing import AsyncGenerator

from src.gateway.protos import gateway_pb2
from src.gateway.protos import gateway_pb2_grpc

logger = logging.getLogger("GatewayClient")

class GatewayClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.channel = None
            cls._instance.stub = None
            cls._instance._channel_loop = None
        return cls._instance

    async def close(self):
        """Closes the gRPC channel."""
        if self.channel:
            await self.channel.close()
            logger.info("GatewayClient gRPC channel closed.")

    def _ensure_connection(self):
        """
        Ensures the gRPC channel exists and is bound to the current event loop.
        """
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("No running event loop found during connection.")
            return

        # Check if we need to reconnect (No channel, or loop mismatch)
        if self.channel is None or self._channel_loop != current_loop:
            if self.channel:
                logger.warning("GatewayClient detected loop mismatch or existing channel. Reconnecting...")
                # We can't safely close the old channel from a new loop if it's bound to the old one,
                # but we can dereference it. The GC will eventually handle it, or we leak a socket.
                # Ideally, we'd schedule a close on the old loop, but we might not have access to it.
                self.channel = None

            host = os.getenv("GATEWAY_HOST", "localhost")
            port = os.getenv("GATEWAY_GRPC_PORT", "50051")
            target = f"{host}:{port}"
            
            logger.info(f"Connecting to Gateway (gRPC) at {target} on loop {id(current_loop)}...")
            self.channel = grpc.aio.insecure_channel(target)
            self.stub = gateway_pb2_grpc.GatewayStub(self.channel)
            self._channel_loop = current_loop
            logger.info("GatewayClient Connected.")

    def connect(self, host=None, port=None):
        # Deprecated: alias to _ensure_connection but params are ignored as we prefer env vars or lazy load
        self._ensure_connection()

    async def execute_tool(self, tool_name: str, params: dict) -> str:
        """
        Calls ExecuteTool via gRPC.
        """
        self._ensure_connection()

        try:
            request = gateway_pb2.ToolRequest(
                tool_name=tool_name,
                params_json=json.dumps(params)
            )
            response = await self.stub.ExecuteTool(request)

            if response.status == "SUCCESS":
                return response.output
            elif response.status == "BLOCKED":
                 return f"BLOCKED: {response.error}"
            else:
                 return f"ERROR: {response.error}"

        except grpc.RpcError as e:
            logger.error(f"gRPC Tool Execution Failed: {e.details()}")
            return f"SYSTEM ERROR: {e.details()}"

    async def chat(self, prompt: str, system_instruction: str | None = None, mode: str = "chat", **kwargs) -> str:
        """
        Invokes LLM via gRPC Chat Endpoint.
        """
        """
        Invokes LLM via gRPC Chat Endpoint.
        """
        self._ensure_connection()

        # Build Message List
        messages = []
        # Add system instruction if provided (though proto has separate field, consistency helps)
        if system_instruction:
            messages.append(gateway_pb2.Message(role="system", content=system_instruction))

        # Add user prompt
        messages.append(gateway_pb2.Message(role="user", content=prompt))

        # Build Request
        request = gateway_pb2.ChatRequest(
            model=kwargs.get("model", "default"),
            messages=messages,
            temperature=kwargs.get("temperature", 0.0),
            system_instruction=system_instruction or "",
            mode=mode,
            guided_json=json.dumps(kwargs.get("guided_json")) if "guided_json" in kwargs else "",
            guided_regex=kwargs.get("guided_regex", ""),
            guided_choice=json.dumps(kwargs.get("guided_choice")) if "guided_choice" in kwargs else ""
        )

        try:
            full_content = []
            # Stream response
            async for response in self.stub.Chat(request):
                full_content.append(response.content)

            return "".join(full_content)

        except grpc.RpcError as e:
            logger.error(f"gRPC Chat Failed: {e.details()}")
            raise e

# Singleton instance
gateway_client = GatewayClient()
