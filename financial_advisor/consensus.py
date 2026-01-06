from typing import Dict, Any, List
import logging
from opentelemetry import trace
from .telemetry import genai_span
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger("ConsensusEngine")
tracer = trace.get_tracer("financial_advisor.consensus")

class ConsensusEngine:
    """
    Layer 4: Consensus Engine (Adaptive Compute).
    Implements a 'Critic' check for high-stakes decisions using a separate LLM call.
    """

    def __init__(self, threshold: float = 10000.0, model_name: str = "gemini-2.5-pro"):
        self.threshold = threshold
        self.model_name = model_name

    def _get_critic_vote(self, role: str, action: str, amount: float, symbol: str) -> str:
        """
        Consults an LLM with a specific critic persona.
        """
        try:
            llm = ChatGoogleGenerativeAI(model=self.model_name, temperature=0.0)

            prompt = f"""
            You are a {role} for a financial institution.
            Review the following trade proposal:
            ACTION: {action}
            AMOUNT: {amount}
            SYMBOL: {symbol}

            Your job is to identify high-risk or irregular activity.
            If the trade looks reasonable for a standard portfolio, say 'APPROVE'.
            If it looks suspicious, reckless, or undefined, say 'REJECT'.

            Format: [DECISION] - [Reason]
            Example: APPROVE - Standard equity purchase.
            """

            response = llm.invoke(prompt)
            content = response.content.strip()

            if "APPROVE" in content:
                return "APPROVE"
            elif "REJECT" in content:
                return "REJECT"
            else:
                return "ESCALATE (Unclear)"

        except Exception as e:
            logger.error(f"Critic {role} failed: {e}")
            return "ERROR"

    def check_consensus(self, action: str, amount: float, symbol: str) -> Dict[str, Any]:
        """
        If the amount > threshold, trigger a consensus check.
        Uses a Multi-Agent Debate pattern (simulated via multiple calls).
        """
        if amount < self.threshold:
            return {"status": "SKIPPED", "reason": "Below threshold"}

        logger.info(f"⚖️ Consensus Engine Triggered for {action} {amount} {symbol}")

        with genai_span("consensus.check", prompt=f"Review trade: {action} {amount} {symbol}") as span:

            # 1. Risk Manager Vote
            vote1 = self._get_critic_vote("Risk Manager", action, amount, symbol)

            # 2. Compliance Officer Vote
            vote2 = self._get_critic_vote("Compliance Officer", action, amount, symbol)

            votes = [vote1, vote2]

            # Consensus Rule: Unanimous Approval Required
            if all(v == "APPROVE" for v in votes):
                decision = "APPROVE"
                reason = "Unanimous approval from Risk and Compliance."
            else:
                decision = "REJECT"
                reason = f"Consensus failed. Votes: {votes}"

            span.set_attribute("consensus.decision", decision)
            span.set_attribute("consensus.votes", str(votes))

            return {"status": decision, "reason": reason, "votes": votes}

consensus_engine = ConsensusEngine()
