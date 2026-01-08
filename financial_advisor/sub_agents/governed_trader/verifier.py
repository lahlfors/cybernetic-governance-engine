from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from pydantic import BaseModel, Field
from typing import List, Literal
from financial_advisor.tools.trades import execute_trade
import json

MODEL = "gemini-2.5-pro"

# Layer 3: Semantic Verification Output Schema
class RiskPacket(BaseModel):
    risk_score: int = Field(..., ge=1, le=100, description="Risk score between 1 (Safe) and 100 (Critical).")
    flags: List[str] = Field(..., description="List of risk flags detected (e.g., 'Financial Threshold Exceeded').")
    decision: Literal["APPROVE", "REJECT", "ESCALATE"] = Field(..., description="Final decision.")
    reasoning: str = Field(..., description="Explanation for the decision.")

def submit_risk_assessment(risk_packet: RiskPacket) -> str:
    """
    Submits the formal risk assessment. This is the Final Verification Step.
    """
    # Handle case where LLM passes a dict instead of a Pydantic model
    if isinstance(risk_packet, dict):
        return json.dumps(risk_packet)
    # In a real system, this might persist to a DB.
    # We return the JSON so the agent's output contains the structured data.
    return json.dumps(risk_packet.model_dump())

from .verifier_prompt import get_verifier_instruction

verifier_agent = LlmAgent(
    name="verifier_agent",
    model=MODEL,
    instruction=get_verifier_instruction(),
    tools=[FunctionTool(execute_trade), FunctionTool(submit_risk_assessment)],
)
