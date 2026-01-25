import logging
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from opentelemetry import trace

from src.utils.telemetry import genai_span

logger = logging.getLogger("ConsensusEngine")
tracer = trace.get_tracer("src.governance.consensus")

class ConsensusEngine:
    """
    Layer 4: Consensus Engine (Adaptive Compute).
    Implements a 'Critic' check for high-stakes decisions using a separate LLM call.
    """

    def __init__(self, threshold: float = 10000.0, model_name: str = "gemini-2.0-pro-exp-02-05"):
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
            If the trade is legitimate but requires human verification (e.g., large withdrawals, complex life events), say 'ESCALATE'.

            Format: [DECISION] - [Reason]
            Example: APPROVE - Standard equity purchase.
            """

            response = llm.invoke(prompt)
            content = response.content.strip()

            if "APPROVE" in content:
                return "APPROVE"
            elif "REJECT" in content:
                return "REJECT"
            elif "ESCALATE" in content:
                return "ESCALATE"
            else:
                return "ESCALATE (Unclear)"

        except Exception as e:
            logger.error(f"Critic {role} failed: {e}")
            return "ERROR"

    def check_consensus(self, action: str, amount: float, symbol: str) -> dict[str, Any]:
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

            # Consensus Rule: REJECT > ESCALATE > APPROVE
            if any(v == "REJECT" for v in votes):
                decision = "REJECT"
                reason = f"Blocked by at least one critic. Votes: {votes}"
            elif any(v == "ESCALATE" or "ESCALATE" in v for v in votes):
                decision = "ESCALATE"
                reason = f"Escalated for human review. Votes: {votes}"
            elif all(v == "APPROVE" for v in votes):
                decision = "APPROVE"
                reason = "Unanimous approval from Risk and Compliance."
            else:
                decision = "ESCALATE"
                reason = f"Consensus unclear. Votes: {votes}"

            span.set_attribute("consensus.decision", decision)
            span.set_attribute("consensus.votes", str(votes))

            return {"status": decision, "reason": reason, "votes": votes}

consensus_engine = ConsensusEngine()
