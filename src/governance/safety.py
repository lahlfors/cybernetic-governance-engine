import logging
import os
from typing import Any, Optional
from google.cloud import firestore
from src.utils.telemetry import get_tracer

logger = logging.getLogger("SafetyLayer")

class ControlBarrierFunction:
    """
    Implements a discrete-time Control Barrier Function (CBF).

    CRITICAL: Uses Firestore for state persistence in Native Architecture.
    We fetch `current_cash` from Firestore for every verification.
    """

    def __init__(self, min_cash_balance: float = 1000.0, gamma: float = 0.5):
        self.min_cash_balance = min_cash_balance
        self.gamma = gamma
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.collection_name = "governance_state"
        self.doc_id = "safety_cbf"

        # Initialize Firestore client (Production Code)
        # Note: In local dev without credentials, this might fail unless emulated.
        try:
            self.db = firestore.Client(project=self.project_id)
            self._initialize_state()
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize Firestore for Safety Filter: {e}")
            self.db = None

        self.tracer = get_tracer()

    def _initialize_state(self):
        """Ensures the initial state exists in Firestore."""
        if not self.db: return

        doc_ref = self.db.collection(self.collection_name).document(self.doc_id)
        try:
            doc = doc_ref.get()
            if not doc.exists:
                doc_ref.set({"current_cash": 100000.0})
                logger.info("Initialized CBF state in Firestore.")
        except Exception as e:
             logger.error(f"Error initializing CBF state: {e}")

    def _get_current_cash(self) -> float:
        """Fetches current cash from Firestore."""
        if not self.db:
             logger.warning("Firestore not connected, returning default safe cash.")
             return 100000.0

        try:
            doc = self.db.collection(self.collection_name).document(self.doc_id).get()
            if doc.exists:
                return float(doc.to_dict().get("current_cash", 100000.0))
        except Exception as e:
            logger.error(f"Error fetching CBF state: {e}")

        return 100000.0

    def get_h(self, cash_balance: float) -> float:
        """
        Safety Function h(x). Safe if h(x) >= 0.
        """
        return cash_balance - self.min_cash_balance

    def verify_action(self, action_name: str, payload: dict[str, Any]) -> str:
        """
        Verifies if the action is safe relative to the *shared* state in Firestore.
        """
        # 1. Fetch State (Hot Path)
        current_cash = self._get_current_cash()

        # Wrap logic in trace
        if self.tracer:
             with self.tracer.start_as_current_span("safety.cbf_check") as span:
                 return self._do_verify_action(action_name, payload, current_cash, span)
        else:
             return self._do_verify_action(action_name, payload, current_cash, None)

    def _do_verify_action(self, action_name: str, payload: dict[str, Any], current_cash: float, span) -> str:
        if span:
             span.set_attribute("safety.cash.current", current_cash)

        # 2. Calculate Next State
        cost = 0.0
        if action_name == "execute_trade":
            # Assuming 'amount' is cash cost for this safety check
            cost = payload.get("amount", 0.0)

        next_cash = current_cash - cost

        # 3. Calculate Barrier
        h_t = self.get_h(current_cash)
        h_next = self.get_h(next_cash)
        required_h_next = (1.0 - self.gamma) * h_t

        logger.info(f"🛡️ CBF Check | Cash: {current_cash} -> {next_cash}")

        # 4. Verify Condition: h(next) >= (1-gamma) * h(current)
        result = "SAFE"
        if h_next < required_h_next or h_next < 0:
             result = f"UNSAFE: CBF violation. h(next)={h_next} < threshold={required_h_next}"

        if span:
             span.set_attribute("safety.cash.next", next_cash)
             span.set_attribute("safety.barrier.h_next", h_next)
             span.set_attribute("safety.result", result)

        return result

    def update_state(self, cost: float):
        """
        Commits the new state to Firestore after successful execution.
        """
        if not self.db: return

        # Use Transaction for consistency
        transaction = self.db.transaction()
        doc_ref = self.db.collection(self.collection_name).document(self.doc_id)

        @firestore.transactional
        def update_in_transaction(transaction, doc_ref):
            snapshot = doc_ref.get(transaction=transaction)
            current = snapshot.to_dict().get("current_cash", 100000.0)
            new_balance = current - cost
            transaction.update(doc_ref, {"current_cash": new_balance})
            logger.info(f"✅ State Updated (Firestore): Cash balance is now {new_balance}")

        try:
            update_in_transaction(transaction, doc_ref)
        except Exception as e:
            logger.error(f"Failed to update CBF state in Firestore: {e}")

# Global instance
safety_filter = ControlBarrierFunction()
