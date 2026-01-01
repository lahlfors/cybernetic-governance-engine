from google.adk.agents import LlmAgent
from pydantic import BaseModel, Field
from typing import List, Literal

MODEL = "gemini-2.5-pro"

# Layer 3: Semantic Verification Output Schema
class RiskPacket(BaseModel):
    risk_score: int = Field(..., ge=1, le=100, description="Risk score between 1 (Safe) and 100 (Critical).")
    flags: List[str] = Field(..., description="List of risk flags detected (e.g., 'Financial Threshold Exceeded').")
    decision: Literal["APPROVE", "REJECT", "ESCALATE"] = Field(..., description="Final decision.")
    reasoning: str = Field(..., description="Explanation for the decision.")

VERIFIER_PROMPT = """
You are a Code Security Auditor and Semantic Verifier.
Your job is to review the actions proposed by the 'Worker' agent.

Rubric:
1.  **Semantic Alignment**: Does the proposed action match the user's intent?
2.  **Safety**: Is the trade amount reasonable and the asset valid?
3.  **Vaporwork**: Does the worker output look like a hallucination?

Output:
You MUST output a JSON object adhering to the following schema:
{
  "risk_score": <int 1-100>,
  "flags": [<string list of flags>],
  "decision": "APPROVE" | "REJECT" | "ESCALATE",
  "reasoning": "<string explanation>"
}

Example:
{
  "risk_score": 10,
  "flags": [],
  "decision": "APPROVE",
  "reasoning": "Trade is within safe limits and matches user intent."
}
"""

verifier_agent = LlmAgent(
    name="verifier_agent",
    model=MODEL,
    instruction=VERIFIER_PROMPT,
    # Note: LlmAgent doesn't natively enforce JSON via Pydantic yet without using tools or specific response_format params.
    # In a full production implementation, we would use response_mime_type="application/json" or Instructor.
    # For now, the system prompt instruction is the constraint.
)
