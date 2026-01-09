from src.utils.telemetry import genai_span
import logging

logger = logging.getLogger("ConsensusLayer")

class ConsensusEngine:
    """
    Layer 4: Consensus Engine (Simulation).
    For high-stakes actions (like trade execution > $10k), this simulates a voting mechanism.
    """
    def __init__(self, threshold=10000):
        self.threshold = threshold

    def check_consensus(self, action: str, amount: float, symbol: str) -> dict:
        """
        Simulates gathering votes from multiple models.
        Returns: {"status": "APPROVE" | "REJECT" | "ESCALATE", "reason": "..."}
        """
        with genai_span("governance.consensus"):
            if amount < self.threshold:
                return {"status": "APPROVE", "reason": "Amount below consensus threshold."}

            logger.info(f"🗳️ Consensus Engine Triggered for {action} {amount} {symbol}")

            # Logic:
            # - If amount > $50k -> ESCALATE (Manual Review)
            # - If amount > $100k -> REJECT (Too risky for auto)
            # - Else -> APPROVE (Simulated 3/3 vote)

            if amount > 100000:
                return {"status": "REJECT", "reason": "Amount exceeds autonomous limit ($100k)."}

            if amount > 50000:
                 return {"status": "ESCALATE", "reason": "High value trade ($50k+) requires human sign-off."}

            return {"status": "APPROVE", "reason": "Consensus reached (3/3 models approved)."}

consensus_engine = ConsensusEngine()
