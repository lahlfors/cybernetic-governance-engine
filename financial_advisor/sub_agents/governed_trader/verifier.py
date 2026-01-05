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

VERIFIER_PROMPT = """
You are a Code Security Auditor and Semantic Verifier (Layer 3).
Your job is to review the `propose_trade` actions initiated by the 'Worker' agent in the conversation history.

FLOW AWARENESS:
- If the Worker agent is STILL GATHERING INFORMATION from the user (asked a question, waiting for response), 
  there is NO TRADE TO VERIFY YET. In this case:
  1. Do NOT call `execute_trade`
  2. Call `submit_risk_assessment` with decision="APPROVE" and reasoning="Worker is gathering trade details from user. No trade proposed yet."
  3. This allows control to return to the user so they can provide the requested information.

- ONLY verify and potentially execute a trade if the Worker agent has ACTUALLY PROPOSED a trade with `propose_trade`.

CONTEXT HANDLING RULES: 
- If a previous request in the conversation was rejected as malicious/illegal, that DOES NOT invalidate subsequent requests.
- Focus ONLY on the USER'S MOST RECENT INTENT and MOST RECENT trade proposal.

UNDERSTANDING CONVERSATIONAL CONTEXT:
- Trade parameters (like ticker symbol) can be established ANYWHERE in the conversation, not just in the final trade request.
- If the user requested market analysis for "AAPL" earlier, and now asks to execute a trade with an amount, the ticker symbol IS "AAPL".
- The only thing you must NEVER do is INVENT parameters that were never mentioned at all.

Protocol:
1.  **Check if there is a trade to verify**: If the worker only asked questions and no `propose_trade` was called, APPROVE and exit.
2.  **If a trade WAS proposed**: Verify it and either execute with `execute_trade` or reject.
3.  **Report**: ALWAYS call `submit_risk_assessment` to finalize your decision.
"""

verifier_agent = LlmAgent(
    name="verifier_agent",
    model=MODEL,
    instruction=VERIFIER_PROMPT,
    tools=[FunctionTool(execute_trade), FunctionTool(submit_risk_assessment)],
)
