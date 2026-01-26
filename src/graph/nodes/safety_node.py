import logging
from typing import Any, Literal

from src.governance.client import opa_client
from src.graph.state import AgentState

logger = logging.getLogger("SafetyNode")

async def safety_check_node(state: AgentState) -> dict[str, Any]:
    """
    Explicit Safety Interceptor Node (Layer 2 Enforcement).
    Intercepts the plan from the Execution Analyst before it reaches the Trader.
    Queries OPA to validate the proposed action.
    """
    logger.info("🛡️ Safety Check Node: Intercepting Execution Plan")

    # 1. Extract the proposed plan/action
    # The Execution Analyst (Planner) outputs a structured plan.
    # We assume the plan is stored in 'execution_plan_output' or inferred from the last message.
    # For this implementation, we look for a structured plan object in the state.

    plan = state.get("execution_plan_output")
    if not plan:
        # If no plan, we assume safety pass (nothing to check) or fail safe.
        # Here we log warning and pass, as the Trader might just be chatting.
        logger.warning("No execution plan found to validate. Passing through.")
        return {"safety_status": "SKIPPED"}

    # 2. Construct the OPA Payload
    # We map the Plan object to the OPA input schema.
    # Assuming 'plan' has 'action', 'amount', 'symbol' etc.
    opa_input = {
        "action": plan.get("action", "unknown"),
        "amount": plan.get("amount", 0),
        "symbol": plan.get("symbol", "UNKNOWN"),
        "user_id": state.get("user_id", "anonymous"),
        "risk_profile": state.get("risk_attitude", "neutral")
    }

    # 3. Query OPA (Governance Layer) - ASYNC
    decision = await opa_client.evaluate_policy(opa_input)

    if decision == "ALLOW":
        logger.info(f"✅ Safety Check PASSED: {opa_input['action']}")
        return {"safety_status": "APPROVED"}

    elif decision == "MANUAL_REVIEW":
        logger.warning(f"⚠️ Safety Check ESCALATED: {opa_input['action']}")
        return {
            "safety_status": "ESCALATED",
            "error": "Governance Policy requires Manual Review."
        }

    elif decision == "UNCERTAIN":
        logger.warning(f"🤔 Safety Check UNCERTAIN: {opa_input['action']}")
        return {
            "safety_status": "UNCERTAIN",
            "risk_feedback": "Governance Policy returned UNCERTAIN. System 2 Analysis required."
        }

    else: # DENY
        logger.critical(f"⛔ Safety Check BLOCKED: {opa_input['action']}")
        return {
            "safety_status": "BLOCKED",
            "error": f"Governance Policy Violation: {opa_input['action']} denied."
        }

def route_safety(state: AgentState) -> Literal["governed_trader", "execution_analyst"]:
    """
    Router for the Safety Node.
    """
    status = state.get("safety_status")

    if status == "APPROVED" or status == "SKIPPED":
        return "governed_trader"

    # If Blocked or Escalated, we route back to the planner (Execution Analyst)
    # to revise the plan or inform the user.
    return "execution_analyst"
