import logging
from typing import Dict, Any, Union
from src.green_agent.agent import green_agent
import json

logger = logging.getLogger("Graph.GreenAgentNode")

def green_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Adapter node for the Green Agent (System 2 Verified Evaluator).
    Intercepts the execution plan, audits it, and determines the next step.
    """
    logger.info("🟢 Green Agent Node: Intercepting Plan for Audit.")

    # 1. Extract the plan from the previous step
    # The graph routes here after 'execution_analyst' or 'risk_analyst'
    # We look for 'execution_plan_output' in the state
    raw_plan = state.get("execution_plan_output")
    history = state.get("messages", [])

    if not raw_plan:
        logger.error("No execution plan found in state!")
        return {
            "green_agent_status": "ERROR",
            "green_agent_feedback": "System Error: No execution plan found to audit."
        }

    # 2. Parse the plan if it's a JSON string (which it might be coming from the model)
    plan_data = {}
    if isinstance(raw_plan, str):
        try:
            # Clean up markdown code blocks if present
            cleaned_plan = raw_plan.replace("```json", "").replace("```", "").strip()
            plan_data = json.loads(cleaned_plan)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse execution plan JSON: {e}")
            return {
                "green_agent_status": "REJECTED_REVISE",
                "green_agent_feedback": f"Format Error: Plan must be valid JSON. Error: {str(e)}"
            }
    elif hasattr(raw_plan, "model_dump"): # Pydantic model
        plan_data = raw_plan.model_dump()
    elif isinstance(raw_plan, dict):
        plan_data = raw_plan
    else:
        # Fallback
        plan_data = {"raw_text": str(raw_plan)}

    # 3. Audit via Green Agent
    audit_result = green_agent.audit_plan(plan_data, history)

    status = audit_result["status"]
    feedback = audit_result["feedback"]

    logger.info(f"🟢 Green Agent Decision: {status}")

    # 4. Update State
    return {
        "green_agent_status": status,
        "green_agent_feedback": feedback,
        # We might want to append a system message to history so the planner sees the feedback
        "messages": [
            # In LangGraph, we typically append messages.
            # Ideally, we construct a ToolMessage or AIMessage.
            # For this simple state dict, we rely on the planner to read 'green_agent_feedback'
        ]
    }
