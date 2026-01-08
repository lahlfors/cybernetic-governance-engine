from typing import Annotated, TypedDict, List, Tuple
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    Shared State for the Financial Advisor Graph.
    Uses 'add_messages' to append chat history rather than overwriting.
    """
    messages: Annotated[List[Tuple[str, str]], add_messages]
