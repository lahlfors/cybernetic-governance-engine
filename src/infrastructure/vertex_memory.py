import os
from typing import Optional
from google.adk.memory import VertexAiMemoryBankService

# Global singleton to be shared between Server (Init) and Agent (Tool/Callback)
_memory_service: Optional[VertexAiMemoryBankService] = None

def get_memory_service() -> Optional[VertexAiMemoryBankService]:
    """
    Returns the initialized memory service singleton.
    Used by PreloadMemoryTool and save_memory_callback.
    """
    global _memory_service
    # Returns None if not initialized (Agent will log warning but continue)
    return _memory_service

def create_memory_service(project_id: str, location: str, engine_id: str) -> VertexAiMemoryBankService:
    """
    Initializes the Vertex AI Memory Bank Service.
    Called by server.py on startup.
    """
    global _memory_service
    if _memory_service is not None:
        return _memory_service

    print(f"🧠 Initializing Vertex AI Memory Bank: {engine_id}")
    try:
        _memory_service = VertexAiMemoryBankService(
            project=project_id,
            location=location,
            agent_engine_id=engine_id
        )
        return _memory_service
    except Exception as e:
        print(f"❌ Failed to create VertexAiMemoryBankService: {e}")
        raise e
