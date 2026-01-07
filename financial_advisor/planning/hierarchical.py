from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class MacroState(Enum):
    """
    High-level states for the HDMDP planner.
    """
    ANALYSIS = auto()      # Gathering data, looking at charts
    STRATEGY = auto()      # Formulating a plan
    RISK_ASSESSMENT = auto() # Verifying safety
    EXECUTION = auto()     # Executing the primitive action

class PrimitiveAction(BaseModel):
    tool_name: str
    tool_args: Dict[str, Any]

class HierarchicalPlanner(ABC):
    """
    Abstract interface for Hierarchical Deterministic MDP Planner.
    The Green Agent uses this to decompose goals.
    """
    @abstractmethod
    def plan_macro_action(self, goal: str, context: Dict[str, Any]) -> MacroState:
        """
        Determines the current macro state based on the goal and context.
        """
        pass

    @abstractmethod
    def expand_primitive_actions(self, macro_state: MacroState, context: Dict[str, Any]) -> List[PrimitiveAction]:
        """
        Expands a macro state into a sequence of primitive tool calls.
        """
        pass

class ExplicitStatePlanner(HierarchicalPlanner):
    """
    A concrete implementation that hardcodes the 'Explicit Routing' logic
    used in the current v1.0 architecture (router.py), but exposed via the
    Planner interface for future HDMDP compatibility.
    """
    def plan_macro_action(self, goal: str, context: Dict[str, Any]) -> MacroState:
        # Simple keyword heuristic mapping (Simulating an intent classifier)
        goal_lower = goal.lower()
        if "analyze" in goal_lower or "price" in goal_lower:
            return MacroState.ANALYSIS
        if "risk" in goal_lower or "audit" in goal_lower:
            return MacroState.RISK_ASSESSMENT
        if "buy" in goal_lower or "sell" in goal_lower:
            # In our governed flow, we don't jump to execution.
            # If we are just starting, we go to Strategy.
            # If we have a strategy, we go to Risk.
            # Only Risk leads to Execution.
            last_state = context.get("last_state")
            if last_state == MacroState.RISK_ASSESSMENT:
                 return MacroState.EXECUTION
            return MacroState.STRATEGY

        return MacroState.ANALYSIS # Default

    def expand_primitive_actions(self, macro_state: MacroState, context: Dict[str, Any]) -> List[PrimitiveAction]:
        if macro_state == MacroState.ANALYSIS:
            return [PrimitiveAction(tool_name="get_market_data", tool_args={"symbol": context.get("symbol", "SPY")})]

        if macro_state == MacroState.STRATEGY:
            return [PrimitiveAction(tool_name="propose_trade", tool_args={})]

        if macro_state == MacroState.RISK_ASSESSMENT:
             return [PrimitiveAction(tool_name="submit_risk_assessment", tool_args={})]

        if macro_state == MacroState.EXECUTION:
             return [PrimitiveAction(tool_name="execute_trade", tool_args=context.get("trade_details", {}))]

        return []
