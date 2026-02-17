
import asyncio
import logging
import os
import json
from concurrent import futures
from typing import Any

import grpc
from nemoguardrails import LLMRails, RailsConfig

# Adjust path so we can import from src if running as script
import sys
sys.path.append(".")

from src.gateway.protos import nemo_pb2
from src.gateway.protos import nemo_pb2_grpc
from src.gateway.governance.nemo.manager import create_nemo_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NeMoSidecar")

# Load Rails Config
# Config is located in config/rails relative to project root (from src/gateway/governance/nemo)
RAILS_CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../config/rails"))

class NeMoService(nemo_pb2_grpc.NeMoGuardrailsServicer):
    def __init__(self):
        self.rails = None
        self._load_rails()

    def _load_rails(self):
        try:
            # Use create_nemo_manager to ensure actions and LLM providers are registered
            if os.path.exists(RAILS_CONFIG_PATH):
                self.rails = create_nemo_manager(RAILS_CONFIG_PATH)
                logger.info(f"✅ NeMo Guardrails loaded from {RAILS_CONFIG_PATH}")
            else:
                logger.warning(f"⚠️ Rails config not found at {RAILS_CONFIG_PATH}")
                # Fallback? No.
        except Exception as e:
            logger.error(f"❌ Failed to load NeMo Guardrails: {e}")
            self.rails = None

    async def Verify(self, request, context):
        if not self.rails:
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details("NeMo Rails not initialized")
            return nemo_pb2.VerifyResponse(status="ERROR")

        try:
            # Generate response using NeMo (Colang flows)
            messages = [{"role": "user", "content": request.input}]

            # TODO: Pass context_json if needed
            response = await self.rails.generate_async(messages=messages)

            content = response.response[0]["content"] if response.response else ""

            return nemo_pb2.VerifyResponse(
                response=content,
                status="SUCCESS"
            )

        except Exception as e:
            logger.error(f"Guardrail execution failed: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return nemo_pb2.VerifyResponse(status="ERROR")

async def serve():
    port = os.getenv("PORT", "8000")
    # For gRPC we often use a different port or share if using multiplexing (harder in python)
    # Let's assume standard gRPC port 50052 for NeMo internal to avoid conflict with HTTP legacy if any?
    # But manifest says 8000. Let's switch NeMo to 50052 in manifest, or reuse 8000 for gRPC.
    # Reusing 8000 for gRPC is fine if we update Client.

    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    nemo_pb2_grpc.add_NeMoGuardrailsServicer_to_server(NeMoService(), server)

    server.add_insecure_port(f'[::]:{port}')
    logger.info(f"🚀 NeMo Guardrails gRPC Server starting on port {port}...")

    await server.start()
    await server.wait_for_termination()

if __name__ == "__main__":
    asyncio.run(serve())
