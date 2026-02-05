from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

def get_checkpointer() -> BaseCheckpointSaver:
    """
    Returns a MemorySaver checkpointer.
    Redis support has been removed in favor of Vertex AI Agent Engine native memory
    or ephemeral memory for this deployment.
    """
    print("✅ Using MemorySaver (Ephemeral/Vertex-Native Compatible)")
    return MemorySaver()
