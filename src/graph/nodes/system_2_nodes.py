import logging
import json
from typing import Any, Dict

from src.causal.engine import ProductionSCM
from src.graph.state import AgentState

logger = logging.getLogger("System2Node")

# Risk Limit for Runtime Checks (can be config)
RUNTIME_RISK_LIMIT = 0.50

async def system_2_simulation_node(state: AgentState) -> Dict[str, Any]:
    """
    System 2 "Rational Fallback" Node.
    Executed when OPA returns UNCERTAIN.
    Uses Causal Engine to simulate the outcome of the proposed action.
    """
    logger.info("🧠 System 2: Starting Causal Simulation (Rational Fallback)")

    # 1. Extract Context and Action
    # We assume context is derived from the user state and plan
    # In a real app, this would be more complex extraction from conversation
    plan = state.get("execution_plan_output")
    if not plan or not isinstance(plan, dict):
        logger.warning("System 2: No execution plan found. Cannot simulate.")
        return {
            "safety_status": "BLOCKED",
            "risk_feedback": "System 2: Missing execution plan."
        }

    action = plan.get("action", "unknown")

    # Context Mapping
    # Extracted from User Profile (state) and Plan
    # In production, we assume upstream nodes (Supervisor) have enriched state with profile data.

    # 1. Transaction Amount (from plan)
    amount = plan.get("amount", 0)

    # 2. Tenure (from profile)
    # If missing, we cannot safely evaluate the "Insult Effect", so we must assume safety or fail.
    # We choose to default to 0.0 (New User) as a conservative baseline for "Insult Effect" (low tenure = low insult risk),
    # but we log the missing data.
    tenure_str = state.get("investment_period", "0") # This is usually 'short-term', not years.
    # Realistically, we need 'tenure_years' in the state.
    # For now, we will look for an explicit 'user_profile' dict if available, or default safe.

    # Check if we have a user object in state
    user_profile = state.get("user_profile", {})
    tenure_years = user_profile.get("tenure_years", 0.0)

    # 3. Location & Fraud (External signals)
    # In a real flow, these come from 'data_analyst' or 'fraud_detector' tools.
    # We check if they exist in state context.
    fraud_risk_score = state.get("fraud_risk_score", 0.0)
    location_mismatch = state.get("location_mismatch", 0)

    context = {
        "Transaction_Amount": amount,
        "Location_Mismatch": location_mismatch,
        "Tenure_Years": tenure_years,
        "Fraud_Risk": fraud_risk_score
    }

    logger.info(f"System 2 Context: Amount={amount}, Tenure={tenure_years}, Fraud={fraud_risk_score}")

    # 2. Map Action to Intervention
    intervention = {}
    if action == "block_transaction":
        intervention["Customer_Friction"] = 0.9
    elif action == "execute_trade":
        # Example: executing trade might increase fraud risk if unchecked?
        # For now, let's say it does nothing to Friction.
        pass
    else:
        logger.info(f"System 2: Action '{action}' has no defined causal intervention. Passing.")
        return {
            "safety_status": "APPROVED",
            "risk_feedback": f"System 2: No causal risk model for {action}."
        }

    # 3. Inference
    engine = ProductionSCM()
    if engine.scm is None:
        logger.error("System 2: Causal Engine not loaded. Fail Closed.")
        return {
            "safety_status": "BLOCKED",
            "risk_feedback": "System 2: Engine unavailable."
        }

    try:
        # We simulate Churn Probability as the key metric for "Blocking" safety
        # Or Fraud Risk for "Allowing"?
        # Let's assume we are checking "Side Effects" -> Churn.
        target = "Churn_Probability"

        risk_score = engine.simulate_intervention(
            context=context,
            intervention=intervention,
            target=target,
            samples=50
        )

        logger.info(f"🧠 System 2 Simulation: Action={action} -> {target}={risk_score:.2f}")

        # 4. Decision
        if risk_score > RUNTIME_RISK_LIMIT:
             logger.warning(f"🧠 System 2 DENY: Risk {risk_score:.2f} > {RUNTIME_RISK_LIMIT}")
             return {
                 "safety_status": "BLOCKED",
                 "risk_feedback": f"System 2 Rational Fallback: Simulation predicts unsafe {target} ({risk_score:.2f}). Action denied."
             }
        else:
             logger.info(f"🧠 System 2 ALLOW: Risk {risk_score:.2f} <= {RUNTIME_RISK_LIMIT}")
             return {
                 "safety_status": "APPROVED",
                 "risk_feedback": f"System 2 Rational Fallback: Simulation predicts safe {target} ({risk_score:.2f})."
             }

    except Exception as e:
        logger.error(f"System 2 Simulation Error: {e}")
        return {
            "safety_status": "BLOCKED",
            "risk_feedback": f"System 2 Error: {e}"
        }
