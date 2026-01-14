from typing import TypedDict, Annotated, List, Literal
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    # The shared conversation history
    messages: Annotated[List[BaseMessage], add_messages]

    # Routing Control
    next_step: Literal["data_analyst", "risk_analyst", "execution_analyst", "governed_trader", "human_review", "FINISH"]

    # Risk Loop Control
    risk_status: Literal["UNKNOWN", "APPROVED", "REJECTED_REVISE"]
    risk_feedback: str | None

    # Green Agent (System 2) Control
    green_agent_status: Literal["UNKNOWN", "APPROVED", "REJECTED", "AUDIT_FAILED"] | None
    green_agent_feedback: str | None
