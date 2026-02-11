"""
Legacy LLM Client Adapter.
Maintained for backward compatibility during refactoring.
"""
from src.gateway.core.llm import GatewayClient

# Alias for legacy imports
HybridClient = GatewayClient
