from enum import Enum, auto
from typing import Dict

class WorkflowState(Enum):
    IDLE = auto()
    MARKET_ANALYSIS_DONE = auto()
    TRADING_STRATEGY_DONE = auto()
    RISK_ASSESSMENT_DONE = auto()
    SESSION_COMPLETE = auto()

class WorkflowEngine:
    def __init__(self):
        self._states: Dict[str, WorkflowState] = {}

    def get_state(self, user_id: str) -> WorkflowState:
        return self._states.get(user_id, WorkflowState.IDLE)

    def transition(self, user_id: str, intent: str) -> str:
        current = self.get_state(user_id)

        if intent == 'MARKET_ANALYSIS':
            self._states[user_id] = WorkflowState.MARKET_ANALYSIS_DONE
            return "Allowed."

        elif intent == 'TRADING_STRATEGY':
            if current == WorkflowState.MARKET_ANALYSIS_DONE:
                self._states[user_id] = WorkflowState.TRADING_STRATEGY_DONE
                return "Allowed."
            elif current == WorkflowState.TRADING_STRATEGY_DONE:
                return "Allowed (Refinement)."
            # Allow loopback from Risk for refinement
            elif current == WorkflowState.RISK_ASSESSMENT_DONE:
                 self._states[user_id] = WorkflowState.TRADING_STRATEGY_DONE
                 return "Allowed (Refinement)."
            raise ValueError("BLOCK: Market Analysis required first.")

        elif intent == 'RISK_ASSESSMENT':
            if current == WorkflowState.TRADING_STRATEGY_DONE:
                self._states[user_id] = WorkflowState.RISK_ASSESSMENT_DONE
                return "Allowed."
            elif current == WorkflowState.RISK_ASSESSMENT_DONE:
                 return "Allowed (Refinement)."
            raise ValueError("BLOCK: Trading Strategy required first.")

        elif intent == 'GOVERNED_TRADING':
            if current == WorkflowState.RISK_ASSESSMENT_DONE:
                self._states[user_id] = WorkflowState.SESSION_COMPLETE
                return "Allowed: Entering High-Stakes Execution."
            raise ValueError("BLOCK: Risk Assessment Approval required first.")

        return "Unknown Intent."

workflow_engine = WorkflowEngine()
