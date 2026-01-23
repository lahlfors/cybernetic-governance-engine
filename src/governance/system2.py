# src/graph/nodes/system2_node.py
from typing import Dict, Any
from src.causal.engine import scm_engine

def system_2_simulation_node(state: Dict[str, Any]):
    """
    Triggered only when OPA is UNCERTAIN.
    Runs the expensive DoWhy simulation.
    """
    print("--- [System 2] Fallback: Running Causal Simulation ---")

    # Extract Context
    context = state.get("context", {})
    action = state.get("proposed_action", "block_transaction") # Default or from state

    # Map Action to Intervention
    intervention = {}
    if action == "block_transaction":
        intervention["Customer_Friction"] = 0.9
    elif action == "execute_trade":
        # Maybe trading increases risk?
        intervention["Fraud_Risk"] = 0.5
    else:
        # Unknown action, default to no-op intervention
        pass

    # Run the heavy simulation (Latency: ~500ms)
    # "If I perform this action, will Churn > 50%?" (Slightly relaxed for runtime stability)
    RISK_LIMIT = 0.50

    try:
        churn_risk = scm_engine.simulate_intervention(
            context=context,
            intervention=intervention,
            target_variable="Churn_Probability",
            num_samples=50
        )

        print(f"   > System 2 Simulation Result: Churn Probability = {churn_risk:.4f}")

        if churn_risk > RISK_LIMIT:
            # Rational Rejection
            return {
                "governance_result": {
                    "status": "DENY",
                    "reason": f"System 2 Simulation predicts high churn ({churn_risk:.2f})"
                }
            }
        else:
            # Rational Approval
            return {
                "governance_result": {
                    "status": "ALLOW",
                    "reason": f"System 2 Simulation predicts safe churn ({churn_risk:.2f})"
                }
            }

    except Exception as e:
        print(f"   !!! System 2 Failed: {e}")
        return {
            "governance_result": {
                "status": "DENY",
                "reason": "System 2 Error"
            }
        }
