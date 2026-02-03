"""
Gateway Client Wrapper (gRPC)
Replaces previous MCP/REST hybrid client with a unified gRPC client.
"""
import logging
import os
import json
import grpc
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

    def connect(self, host=None, port=None):
        if not host:
            host = os.getenv("GATEWAY_HOST", "localhost")
        if not port:
            port = os.getenv("GATEWAY_PORT", "50051")

        target = f"{host}:{port}"
        logger.info(f"Connecting to Gateway gRPC at {target}...")

        # Create Channel (Insecure for internal cluster)
        # Using AIO Channel for async support
        self.channel = grpc.aio.insecure_channel(target)
        self.stub = gateway_pb2_grpc.GatewayStub(self.channel)

    async def execute_tool(self, tool_name: str, params: dict) -> str:
        """
        Calls a Tool on the Gateway Server via gRPC.
        """
        if not self.stub:
            self.connect()

        try:
            params_json = json.dumps(params)
            request = gateway_pb2.ToolRequest(
                tool_name=tool_name,
                params_json=params_json
            )
            response = await self.stub.ExecuteTool(request)

            if response.status == "SUCCESS":
                return response.output
            elif response.status == "BLOCKED":
                 return f"BLOCKED: {response.error}"
            else: # ERROR
                 return f"ERROR: {response.error}"

        except grpc.RpcError as e:
            logger.error(f"gRPC Tool Error: {e.code()} - {e.details()}")
            return f"SYSTEM ERROR: Could not call Gateway. {e.details()}"

    async def chat(self, prompt: str, system_instruction: str = None, mode: str = "chat", **kwargs) -> str:
        """
        Invokes LLM via Gateway gRPC Endpoint.
        """
        if not self.stub:
            self.connect()

        messages = []
        # Support history if passed? The current interface just takes 'prompt'.
        # We wrap the prompt as a single user message.
        messages.append(gateway_pb2.Message(role="user", content=prompt))

        # Pack kwargs
        request_kwargs = {
            "model": kwargs.get("model", "default"),
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.0),
            "mode": mode,
            "system_instruction": system_instruction
        }

        if "guided_json" in kwargs:
             request_kwargs["guided_json"] = json.dumps(kwargs["guided_json"])
        if "guided_regex" in kwargs:
             request_kwargs["guided_regex"] = kwargs["guided_regex"]
        if "guided_choice" in kwargs:
             request_kwargs["guided_choice"] = json.dumps(kwargs["guided_choice"])

        request = gateway_pb2.ChatRequest(**request_kwargs)

        try:
            response_stream = self.stub.Chat(request)
            full_content = []
            async for chunk in response_stream:
                full_content.append(chunk.content)

            return "".join(full_content)

        except grpc.RpcError as e:
             logger.error(f"gRPC Chat Error: {e.code()} - {e.details()}")
             # Propagate as a runtime error for the agent to handle
             raise RuntimeError(f"Gateway Chat Failed: {e.details()}")

# Singleton instance
gateway_client = GatewayClient()
