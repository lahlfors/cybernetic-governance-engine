from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field
import json
import logging

# Logic Imports
from financial_advisor.governance.constitution import Constitution
from financial_advisor.governance.opa_reasoner import OPAReasoner
from financial_advisor.tools.trades import execute_trade as original_execute_trade

logger = logging.getLogger("GreenAgent")

# --- Schemas ---
class RiskPacket(BaseModel):
    risk_score: int = Field(..., ge=1, le=100, description="Risk score between 1 (Safe) and 100 (Critical).")
    flags: List[str] = Field(..., description="List of risk flags detected (e.g., 'Financial Threshold Exceeded').")
    decision: Literal["APPROVE", "REJECT", "ESCALATE"] = Field(..., description="Final decision.")
    reasoning: str = Field(..., description="Explanation for the decision.")

class SimulationResult(BaseModel):
    safe: bool
    projected_balance: Optional[float] = None
    violation_reason: Optional[str] = None

# --- Service Class ---
class GreenAgentService:
    """
    The 'Green Agent' (Layer 3 & System 2).
    It replaces the simple 'verifier_agent' with a service that enforces
    Constitution compliance and simulates outcomes.
    """
    def __init__(self, constitution: Optional[Constitution] = None):
        self.constitution = constitution or Constitution(reasoner=OPAReasoner())

    def submit_risk_assessment(self, risk_packet: RiskPacket) -> str:
        """
        Submits the formal risk assessment.
        """
        if isinstance(risk_packet, dict):
             # Try to parse it to ensure validity
             try:
                 risk_packet = RiskPacket(**risk_packet)
             except Exception as e:
                 return f"ERROR: Invalid Risk Packet format: {e}"

        return json.dumps(risk_packet.model_dump())

    def simulate_outcome(self, action_name: str, payload: Dict[str, Any]) -> SimulationResult:
        """
        System 2: Projects the future state.
        Currently implements a basic arithmetic projection for 'execute_trade'.
        Future Roadmap: Use Mamba/World Model for complex simulations.
        """
        if action_name == "execute_trade":
            # 1. Get current state (Mocked for now, in real system read from safety/Redis)
            current_cash = 100000.0 # Mock: Start with $100k

            # 2. Get action details
            amount = payload.get("amount", 0)

            # 3. Project
            projected_cash = current_cash - amount

            # 4. Check Safety (Hard constraint: No debt)
            if projected_cash < 0:
                return SimulationResult(
                    safe=False,
                    projected_balance=projected_cash,
                    violation_reason="Insolvency Risk: Trade would result in negative balance."
                )

            return SimulationResult(safe=True, projected_balance=projected_cash)

        return SimulationResult(safe=True) # Default safe for non-financial actions

    def verify_and_execute(self, action_name: str, payload: Dict[str, Any]) -> str:
        """
        The Core Loop: Project -> Verify -> Act
        """
        # 1. Project / Simulate
        simulation = self.simulate_outcome(action_name, payload)
        if not simulation.safe:
            msg = f"BLOCKED by Green Agent Simulation: {simulation.violation_reason}"
            logger.warning(msg)
            return msg

        # 2. Constitutional Check (Redundant but necessary for defense-in-depth)
        policy_result = self.constitution.check_action(action_name, payload)
        if not policy_result.allowed:
            return f"BLOCKED by Constitution: {policy_result.reason}"

        # 3. Execute
        if action_name == "execute_trade":
            # We call the original tool, which ALSO has the OPA decorator (Layer 2)
            # The Green Agent adds Layer 3 (Simulation) on top.
            return original_execute_trade(**payload)

        return f"Action {action_name} not supported by Green Agent execution layer."

# --- Agent Wrapper for Google ADK ---
# This keeps the LlmAgent interface for the orchestration layer
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

# We instantiate the service
green_service = GreenAgentService()

# We define wrapper functions for the tools so the LLM can call them
def green_submit_assessment(risk_packet: RiskPacket) -> str:
    return green_service.submit_risk_assessment(risk_packet)

def green_execute_trade(symbol: str, amount: int, action: str, transaction_id: str, trader_id: str, trader_role: str) -> str:
    """
    Executes a trade AFTER Green Agent simulation and verification.
    """
    payload = {
        "symbol": symbol,
        "amount": amount,
        "action": action,
        "transaction_id": transaction_id,
        "trader_id": trader_id,
        "trader_role": trader_role
    }
    return green_service.verify_and_execute("execute_trade", payload)

GREEN_AGENT_PROMPT = """
You are the Green Agent (Layer 3 Verifier).
Your goal is to audit the Worker Agent's proposed trades.

RULES:
1. Review the conversation.
2. If the user provided the amount, and the trade makes sense, calls `green_execute_trade`.
3. If the amount is made up, REJECT.
4. Always call `green_submit_assessment` with your decision.
"""

green_agent = LlmAgent(
    name="green_agent", # Renamed from verifier_agent
    model="gemini-2.5-pro",
    instruction=GREEN_AGENT_PROMPT,
    tools=[FunctionTool(green_execute_trade), FunctionTool(green_submit_assessment)],
)
