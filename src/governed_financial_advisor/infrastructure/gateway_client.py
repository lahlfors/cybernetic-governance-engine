"""
Gateway Client Wrapper (Async)
"""
import grpc.aio
import json
import logging
import os

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
        return cls._instance

    def connect(self, host="localhost", port=50051):
        if not self.channel:
            target = f"{host}:{port}"
            self.channel = grpc.aio.insecure_channel(target)
            self.stub = gateway_pb2_grpc.GatewayStub(self.channel)
            logger.info(f"Connected to Gateway at {target}")

    async def execute_tool(self, tool_name: str, params: dict) -> str:
        if not self.stub:
            self.connect()

        req = gateway_pb2.ToolRequest(
            tool_name=tool_name,
            params_json=json.dumps(params)
        )

        try:
            resp = await self.stub.ExecuteTool(req)
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
            call = self.stub.Chat(req)
            async for resp in call:
                full_text.append(resp.content)

            return "".join(full_text)
        except grpc.aio.AioRpcError as e:
            logger.error(f"Chat RPC Failed: {e}")
            raise e

# Singleton instance
gateway_client = GatewayClient()
