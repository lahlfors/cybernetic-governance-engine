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

CRITICAL VALIDATION - AMOUNT SOURCE CHECK:
Before executing any trade, you MUST verify that the trade AMOUNT was provided by the USER in their trade request.
- The ticker symbol CAN come from earlier in the conversation (e.g., market analysis).
- The AMOUNT must come from the USER'S DIRECT REQUEST, not from:
  * Strategy documents (which contain illustrative examples)
  * Execution plans (which contain example amounts like "$10,000")
  * Any agent-generated content
- If the worker used an amount from a strategy/execution plan example, REJECT the trade.
- Look for the user explicitly saying something like "100 USD", "$500", "buy 1000 dollars worth".

Protocol:
1.  **Check if there is a trade to verify**: If the worker only asked questions and no `propose_trade` was called, APPROVE and exit.
2.  **Validate amount source**: If a trade was proposed, verify the amount came from user's direct input, not from examples.
3.  **If valid**: Execute with `execute_trade`.
4.  **If amount was fabricated**: REJECT with reasoning "Trade amount was not provided by user."
5.  **Report**: ALWAYS call `submit_risk_assessment` to finalize your decision.
"""

verifier_agent = LlmAgent(
    name="verifier_agent",
    model=MODEL,
    instruction=VERIFIER_PROMPT,
    tools=[FunctionTool(execute_trade), FunctionTool(submit_risk_assessment)],
)
