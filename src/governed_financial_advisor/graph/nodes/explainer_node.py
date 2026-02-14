import logging
from typing import Any

from src.governed_financial_advisor.agents.explainer.agent import create_explainer_agent
from src.governed_financial_advisor.graph.nodes.adapters import run_adk_agent
from src.governed_financial_advisor.graph.state import AgentState

logger = logging.getLogger("ExplainerNode")

async def explainer_node(state: AgentState) -> dict[str, Any]:
    """
    Runs the Explainer Agent to generate the final response.
    """
    logger.info("🗣️ Explainer Node: Generating final response.")

    agent = create_explainer_agent()

    # Context is implicitly in the state history, but we can reinforce it
    user_msg = "Please generate the final report for the user."

    response = run_adk_agent(agent, user_msg, state["user_id"], "session_explainer")

    # The Explainer's text is the final answer
    return {
        "messages": [("ai", response.answer)],
        "next_step": "FINISH"
    }
