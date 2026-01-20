from typing import TypedDict, Annotated, List, Literal, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from src.governance.stpa import ControlLoop

class AgentState(TypedDict):
    # The shared conversation history
    messages: Annotated[List[BaseMessage], add_messages]

    # Routing Control
    next_step: Literal["data_analyst", "risk_analyst", "execution_analyst", "governed_trader", "human_review", "FINISH"]

    # Risk Loop Control
    risk_status: Literal["UNKNOWN", "APPROVED", "REJECTED_REVISE"]
    risk_feedback: str | None

    # STPA Control Context
    control_loop_metadata: Optional[ControlLoop] # Current STPA context

    # User Profile
    risk_attitude: str | None
    investment_period: str | None

    execution_plan_output: str | dict | None # Holds the structured plan
    user_id: str # User Identity
