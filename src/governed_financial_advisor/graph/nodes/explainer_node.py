import logging
from typing import Any

from litellm import acompletion
from config.settings import Config, MODEL_FAST
from src.governed_financial_advisor.graph.state import AgentState
from src.governed_financial_advisor.utils.text_utils import strip_thinking_tags

logger = logging.getLogger("ExplainerNode")

async def explainer_node(state: AgentState) -> dict[str, Any]:
    """
    Runs the Explainer Agent to generate the final response.
    Uses direct LiteLLM call to avoid ADK Runner overhead/connection issues.
    """
    logger.info("🗣️ Explainer Node: Generating final response (Direct LiteLLM).")

    # Construct the prompt manually since we are bypassing the Agent/Prompt object
    # We want to summarize the execution results.
    
    execution_plan = state.get("execution_plan_output")
    execution_result = "No execution result." # Placeholder if we don't have it in state? 
    # Actually, the previous node was Evaluator. 
    # If we are here, it means Evaluator APPROVED.
    # But Evaluator doesn't execute?
    # Wait, the flow is: Plan -> Review -> Execute -> Explain?
    # Or Plan -> Review -> Explain (if just planning)?
    # The prompt in agent.py assumes "execution_result".
    
    # For now, let's just ask it to explain the plan and the approval.
    
    user_msg = (
        "You are the **Explainer Agent**. Your role is to formulate the final response to the user.\n"
        "The proposed plan has been **APPROVED** by the internal Safety & Governance checks.\n\n"
        f"USER MESSAGE: {state['messages'][-1].content if state['messages'] else 'No user message'}\n\n"
        f"APPROVED PLAN: {execution_plan}\n\n"
        "Please generate a professional response confirming the strategy/action to the user.\n"
        "Include a standard financial disclaimer."
    )

    try:
        response = await acompletion(
            model=MODEL_FAST, 
            api_base=Config.VLLM_FAST_API_BASE,
            api_key="EMPTY",
            messages=[{"role": "user", "content": user_msg}]
        )
        content = strip_thinking_tags(response.choices[0].message.content)
        
        return {
            "messages": [("ai", content)], 
            "next_step": "FINISH"
        }
    except Exception as e:
        logger.error(f"Error in ExplainerNode (Direct LiteLLM): {e}")
        return {
            "messages": [("ai", f"Error generating explanation: {e}")],
            "next_step": "FINISH"
        }

