
import asyncio
import logging
import os
from concurrent import futures
from typing import Any

import grpc
import nest_asyncio
from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.context import streaming_handler_var

# Adjust path so we can import from src if running as script
import sys
sys.path.append(".")

from src.gateway.protos import nemo_pb2
from src.gateway.protos import nemo_pb2_grpc
from src.gateway.governance.nemo.manager import create_nemo_manager
from src.gateway.governance.nemo.exporter import NeMoOTelCallback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Gateway.NeMo.Server")

# Load Rails Config
RAILS_CONFIG_PATH = os.getenv("RAILS_CONFIG_PATH", "config/rails")

class NeMoService(nemo_pb2_grpc.NeMoGuardrailsServicer):
    def __init__(self):
        self.rails = None
        self._load_rails()

    def _load_rails(self):
        try:
            self.rails = create_nemo_manager(RAILS_CONFIG_PATH)
            logger.info(f"✅ NeMo Guardrails loaded from {RAILS_CONFIG_PATH}")
        except Exception as e:
            logger.error(f"❌ Failed to load NeMo Guardrails: {e}")
            self.rails = None

    async def Verify(self, request, context):
        if not self.rails:
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details("NeMo Rails not initialized")
            return nemo_pb2.VerifyResponse(status="ERROR")

        # ISO 42001: Attach OTel Callback
        handler = NeMoOTelCallback()
        token = streaming_handler_var.set(handler)

        try:
            # Generate response using NeMo (Colang flows)
            messages = [{"role": "user", "content": request.input}]

            logger.info(f"Processing NeMo Request: {request.input[:50]}...")

            # Pass handler for observability
            response = await self.rails.generate_async(
                messages=messages,
                streaming_handler=handler
            )

            content = ""
            if isinstance(response, dict):
                content = response.get("content", "")
                if not content and "response" in response:
                     content = response["response"][0]["content"]
            elif hasattr(response, "response"):
                content = response.response[0]["content"]
            else:
                content = str(response)

            status = "SUCCESS"
            if "I cannot" in content or "policy" in content.lower():
                status = "BLOCKED"

            return nemo_pb2.VerifyResponse(
                response=content,
                status=status
            )

        except Exception as e:
            logger.error(f"Guardrail execution failed: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return nemo_pb2.VerifyResponse(status="ERROR")
        finally:
            streaming_handler_var.reset(token)

async def serve():
    nest_asyncio.apply()
    port = os.getenv("PORT", "8000")

    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    nemo_pb2_grpc.add_NeMoGuardrailsServicer_to_server(NeMoService(), server)

    server.add_insecure_port(f'[::]:{port}')
    logger.info(f"🚀 NeMo Guardrails gRPC Server starting on port {port}...")

    await server.start()
    await server.wait_for_termination()

if __name__ == "__main__":
    asyncio.run(serve())
