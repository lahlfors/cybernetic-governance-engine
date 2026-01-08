from typing import TypedDict, Annotated, List, Optional
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict):
    """
    The Cybernetic State.
    Tracks the artifacts strictly required for the HD-MDP transition.
    """
    # Conversation History
    messages: Annotated[List[BaseMessage], operator.add]

    # The 'Blackboard' - specific artifacts for each stage
    market_data: Optional[str]      # Output of Stage 1
    trading_strategy: Optional[str] # Output of Stage 2
    risk_assessment: Optional[str]  # Output of Stage 3

    # Feedback Loop Control
    feedback: Optional[str]         # Critique from Risk Node
    revision_count: Annotated[int, operator.add] # Circuit Breaker (increments automatically)

    # Metadata
    user_id: str
