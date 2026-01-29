from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    # The shared conversation history
    messages: Annotated[list[BaseMessage], add_messages]

    # Routing Control
    next_step: Literal["data_analyst", "risk_analyst", "execution_analyst", "governed_trader", "human_review", "FINISH"]

    # Risk Loop Control
    risk_status: Literal["UNKNOWN", "APPROVED", "REJECTED_REVISE"]
    risk_feedback: str | None

    # Safety & Optimization Control
    safety_status: Literal["APPROVED", "BLOCKED", "ESCALATED", "SKIPPED"]
    trader_prep_output: dict[str, Any] | None

    # User Profile
    risk_attitude: str | None
    investment_period: str | None

    # Execution Data
    execution_plan_output: str | dict | None # Holds the structured plan
    user_id: str # User Identity
    
    # Telemetry
    latency_stats: dict[str, float] | None # For Bankruptcy Protocol (cumulative spend)
