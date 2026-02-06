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
        return cls._instance

    async def close(self):
        """Closes the gRPC channel."""
        if self.channel:
            await self.channel.close()
            logger.info("GatewayClient gRPC channel closed.")

    def connect(self, host=None, port=None):
        if self.channel:
            return

        if not host:
            host = os.getenv("GATEWAY_HOST", "localhost")
        if not port:
            port = os.getenv("GATEWAY_PORT", "50051")

        target = f"{host}:{port}"
        logger.info(f"Connecting to Gateway (gRPC) at {target}...")

        # Insecure for internal cluster traffic (efficient)
        self.channel = grpc.aio.insecure_channel(target)
        self.stub = gateway_pb2_grpc.GatewayStub(self.channel)
        logger.info("GatewayClient Connected.")

    async def execute_tool(self, tool_name: str, params: dict) -> str:
        """
        Calls ExecuteTool via gRPC.
        """
        if not self.stub:
            self.connect()

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
        if not self.stub:
            self.connect()

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
