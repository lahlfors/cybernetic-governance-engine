# src/causal/nodes.py
from src.causal.engine import scm_engine
from typing import Dict, Any

def intervention_simulation_node(state: Dict[str, Any]):
    print("--- [Node C] Intervention Simulation: Real Inference ---")

    # In LangGraph, state usually has keys. Adjust based on where this is called.
    # Assuming 'state' is the AgentState dict.
    # We need to map AgentState to the Causal Graph Variables.
    # For this demo, let's assume the state has a 'context' key or specific keys
    # that map to our graph nodes: 'Transaction_Amount', 'Location_Mismatch', 'Tenure_Years'.

    # Check if 'context' exists, else try to build it from flat state
    context = state.get("context", {})
    if not context:
        # Fallback: try to extract from state if keys exist directly
        possible_keys = ['Transaction_Amount', 'Location_Mismatch', 'Tenure_Years', 'Fraud_Risk']
        for k in possible_keys:
            if k in state:
                context[k] = state[k]

    # If still empty, provide defaults to prevent crash (though in real life we might error out)
    if not context:
        print("!!! Warning: No context found in state for Causal Inference. Using defaults.")
        context = {
            'Transaction_Amount': 100.0,
            'Location_Mismatch': 0,
            'Tenure_Years': 5.0
        }

    # 1. Map "Business Action" to "Graph Node Intervention"
    # Action: "Block Transaction" -> Graph Node: "Customer_Friction" goes High (0.9)
    # The 'action' might be in the state.
    proposed_action = state.get("proposed_action", "BLOCK") # Defaulting to testing the BLOCK action

    intervention = {}
    if proposed_action == "BLOCK":
        intervention["Customer_Friction"] = 0.9
    elif proposed_action == "APPROVE":
        intervention["Customer_Friction"] = 0.1
    else:
        # Default to high friction if unknown action for safety? Or low?
        intervention["Customer_Friction"] = 0.5


    # 2. Run Real Simulation
    try:
        predicted_churn = scm_engine.simulate_intervention(
            context=context,
            intervention=intervention,
            target_variable="Churn_Probability",
            num_samples=50 # Lower samples = faster speed
        )
    except Exception as e:
        print(f"!!! Causal Inference Failed: {e}")
        predicted_churn = 0.0 # Fail-open (don't block if we can't reason)

    print(f"   > SIMULATION: P(Churn | do({proposed_action})) = {predicted_churn:.4f}")

    # 3. Governance Logic (Threshold Check)
    # If the predicted churn is too high, we might want to override a BLOCK decision.

    risk_score = context.get("Fraud_Risk", 0.0)

    # Decision Logic:
    # If we intended to BLOCK (high friction), but Churn is too high, we might reconsider
    # if the fraud risk isn't EXTREME.

    decision = "APPROVE_BLOCK" # Default approval of the blocking action

    # "Constraint: If P(Churn | do(Block)) > 0.15 AND Risk < 0.90, divert..."
    if proposed_action == "BLOCK":
        if risk_score < 0.90 and predicted_churn > 0.15:
            print("   > GOVERNANCE INTERCEPT: Churn risk too high for this fraud score. Overriding.")
            decision = "DENY_BLOCK" # We deny the permission to block
        else:
            print("   > GOVERNANCE: Blocking approved.")

    return {
        "causal_analysis": {"predicted_churn": predicted_churn},
        "final_decision": decision
    }
