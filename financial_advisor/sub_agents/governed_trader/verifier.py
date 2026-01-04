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
    # In a real system, this might persist to a DB.
    # We return the JSON so the agent's output contains the structured data.
    return json.dumps(risk_packet.model_dump())

VERIFIER_PROMPT = """
You are a Code Security Auditor and Semantic Verifier (Layer 3).
Your job is to review the `propose_trade` actions initiated by the 'Worker' agent in the conversation history.

Protocol:
1.  **Analyze**: Review the worker's proposal for Semantic Alignment, Safety, and Vaporwork.
2.  **Verify**:
    - If SAFE: Call `execute_trade` with the EXACT details from the proposal.
    - If UNSAFE or High Risk: Do NOT call `execute_trade`.
3.  **Report**: ALWAYS call `submit_risk_assessment` to finalize your decision.

You must ALWAYS end by calling `submit_risk_assessment`.
If you approved and executed the trade, the decision in the packet should be "APPROVE".
If you blocked it, the decision should be "REJECT" or "ESCALATE".
"""

verifier_agent = LlmAgent(
    name="verifier_agent",
    model=MODEL,
    instruction=VERIFIER_PROMPT,
    tools=[FunctionTool(execute_trade), FunctionTool(submit_risk_assessment)],
)
