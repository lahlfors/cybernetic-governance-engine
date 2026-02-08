from typing import Any, Literal, TypedDict, List
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    # The shared conversation history
    messages: List[BaseMessage]

    # Routing Control
    next_step: Literal[
        "data_analyst",
        "execution_analyst",
        "evaluator",
        "governed_trader",
        "explainer",
        "human_review",
        "FINISH"
    ]

    # Risk Loop Control
    risk_status: Literal["UNKNOWN", "APPROVED", "REJECTED_REVISE"]
    risk_feedback: str | None

    # Safety & Optimization Control
    safety_status: Literal["APPROVED", "BLOCKED", "ESCALATED", "SKIPPED"]

    # User Profile
    risk_attitude: str | None
    investment_period: str | None

    # Execution Data
    execution_plan_output: str | dict | None # Holds the structured plan (System 4 Output)

    # MACAW / System 3 Control Signals
    evaluation_result: dict[str, Any] | None # The Evaluator's Verdict & Simulation Results
    execution_result: dict[str, Any] | None # The Executor's Technical Output (System 1)

    user_id: str # User Identity

    # Telemetry
    latency_stats: dict[str, float] | None # For Bankruptcy Protocol (cumulative spend)
