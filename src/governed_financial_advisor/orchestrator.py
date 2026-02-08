# src/governed_financial_advisor/orchestrator.py

import logging
import asyncio
from typing import Dict, Any, List

from langchain_core.messages import HumanMessage, BaseMessage

# Import State
from src.governed_financial_advisor.graph.state import AgentState

# Import Nodes
from src.governed_financial_advisor.graph.nodes.supervisor_node import supervisor_node
from src.governed_financial_advisor.graph.nodes.adapters import (
    data_analyst_node,
    execution_analyst_node,
    governed_trader_node
)
from src.governed_financial_advisor.graph.nodes.evaluator_node import evaluator_node
from src.governed_financial_advisor.graph.nodes.explainer_node import explainer_node

logger = logging.getLogger("Orchestrator")

class FinancialAdvisorOrchestrator:
    """
    Custom Orchestrator to replace LangGraph.
    Implements the MACAW flow: Supervisor -> Planner -> Evaluator -> Trader -> Explainer.
    """

    def __init__(self):
        pass

    def run(self, prompt: str, user_id: str = "default_user", thread_id: str = "default_thread") -> Dict[str, Any]:
        """
        Executes the agent workflow synchronously (blocking).
        """
        # 1. Initialize State
        state: AgentState = {
            "messages": [HumanMessage(content=prompt)],
            "next_step": "supervisor",
            "risk_status": "UNKNOWN",
            "risk_feedback": None,
            "safety_status": "APPROVED",
            "risk_attitude": None,
            "investment_period": None,
            "execution_plan_output": None,
            "evaluation_result": None,
            "execution_result": None,
            "user_id": user_id,
            "latency_stats": {}
        }

        loop_count = 0
        max_loops = 15 # Prevent infinite loops

        while loop_count < max_loops:
            current_step = state["next_step"]
            logger.info(f"--- [Orchestrator] Step: {current_step} (Loop {loop_count}) ---")

            if current_step == "FINISH":
                break

            # Execute Node
            if current_step == "supervisor":
                # Supervisor determines next step based on intent
                output = supervisor_node(state)
                self._update_state(state, output)

            elif current_step == "data_analyst":
                output = data_analyst_node(state)
                self._update_state(state, output)
                # Data Analyst always returns to Supervisor in original graph
                state["next_step"] = "supervisor"

            elif current_step == "execution_analyst":
                output = execution_analyst_node(state)
                self._update_state(state, output)
                # Planner always goes to Evaluator
                state["next_step"] = "evaluator"

            elif current_step == "evaluator":
                # Evaluator is async
                output = asyncio.run(evaluator_node(state))
                self._update_state(state, output)
                # Evaluator sets next_step to 'governed_trader' (Approved) or 'execution_analyst' (Rejected)

            elif current_step == "governed_trader":
                output = governed_trader_node(state)
                self._update_state(state, output)
                # Trader goes to Explainer
                state["next_step"] = "explainer"

            elif current_step == "explainer":
                # Explainer is async
                output = asyncio.run(explainer_node(state))
                self._update_state(state, output)
                 # Explainer usually finishes or goes back to Supervisor
                if output.get("next_step") == "FINISH":
                    state["next_step"] = "FINISH"
                else:
                     state["next_step"] = "supervisor"

            elif current_step == "human_review":
                # Placeholder for now
                logger.info("--- [Orchestrator] Human Review Requested ---")
                state["next_step"] = "supervisor"

            else:
                logger.error(f"Unknown step: {current_step}")
                break

            loop_count += 1

        return state

    def _update_state(self, state: AgentState, output: Dict[str, Any]):
        """Updates the state with output from a node."""
        if not output:
            return

        # Update messages
        if "messages" in output:
            new_msgs = output["messages"]
            # Append if not already present (simplified)
            # In LangGraph add_messages handles IDs, here we just append.
            # Nodes return dict with 'messages': [...]
            for m in new_msgs:
                if isinstance(m, tuple): # (role, content)
                    role, content = m
                    if role == "ai":
                         # We don't have AIMessage imported easily here without langchain_core
                         # But let's assume we can struct it or just use simple dicts if downstreams allow
                         # Ideally we keep using BaseMessage types.
                         from langchain_core.messages import AIMessage
                         state["messages"].append(AIMessage(content=content))
                else:
                    state["messages"].append(m)

        # Update other keys
        for k, v in output.items():
            if k != "messages":
                state[k] = v
