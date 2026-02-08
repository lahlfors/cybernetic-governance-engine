"""
HybridClient: Refactored to be a Client Stub for the Agentic Gateway.
Delegates all calls to the gRPC Gateway Service.

DEPRECATED: New code should use `src.governed_financial_advisor.infrastructure.gateway_client` directly.
This stub is maintained for backward compatibility during the refactor.
"""

import logging
from src.governed_financial_advisor.infrastructure.gateway_client import gateway_client

logger = logging.getLogger(__name__)

class HybridClient:
    def __init__(
        self,
        vllm_base_url: str = None,
        vllm_api_key: str = None,
        vllm_model: str = None,
        vertex_model: str = None,
        vertex_project: str | None = None,
        vertex_location: str = None,
        fallback_threshold_ms: float = 200.0
    ):
        logger.info("Initializing HybridClient (Gateway Stub)...")
        gateway_client.connect()

    async def generate(self, prompt: str, system_instruction: str = None, mode: str = "chat", **kwargs) -> str:
        """
        Delegates generation to the Gateway via gRPC.
        """
        return await gateway_client.chat(prompt, system_instruction, mode, **kwargs)

    @property
    def vertex_client(self):
        raise NotImplementedError("Direct Vertex Client access is deprecated. Use .generate() via Gateway.")
