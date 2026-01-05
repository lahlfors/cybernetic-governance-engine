from typing import Dict, Any, List
import logging
from opentelemetry import trace
from .telemetry import genai_span

logger = logging.getLogger("ConsensusEngine")
tracer = trace.get_tracer("financial_advisor.consensus")

class ConsensusEngine:
    """
    Layer 4: Consensus Engine (Adaptive Compute).
    Simulates ensemble voting for high-stakes decisions.
    """

    def __init__(self, threshold: float = 10000.0):
        self.threshold = threshold

    def check_consensus(self, action: str, amount: float, symbol: str) -> Dict[str, Any]:
        """
        If the amount > threshold, trigger a consensus check.
        In a real system, this would call multiple LLMs (GPT-4, Claude, etc.).
        Here, we simulate it or just log the check.
        """
        if amount < self.threshold:
            return {"status": "SKIPPED", "reason": "Below threshold"}

        logger.info(f"⚖️ Consensus Engine Triggered for {action} {amount} {symbol}")

        with genai_span("consensus.check", prompt=f"Review trade: {action} {amount} {symbol}") as span:
            # Simulate voting
            votes = ["APPROVE", "APPROVE", "APPROVE"] # In reality, query models

            disagree = [v for v in votes if v != "APPROVE"]

            if disagree:
                decision = "REJECT"
                reason = f"Consensus failed. Votes: {votes}"
            else:
                decision = "APPROVE"
                reason = "Unanimous approval."

            span.set_attribute("consensus.decision", decision)
            span.set_attribute("consensus.votes", str(votes))

            return {"status": decision, "reason": reason, "votes": votes}

consensus_engine = ConsensusEngine()
