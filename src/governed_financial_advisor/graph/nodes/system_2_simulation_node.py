# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
System 2 Simulation Node (Rational Fallback)

This node is triggered when OPA returns UNCERTAIN.
It uses the Causal Engine to probabilistically evaluate the risk of the proposed action.
"""

import logging
from typing import Any, Dict

from src.causal.engine import ProductionSCM
from src.governed_financial_advisor.graph.state import AgentState

logger = logging.getLogger("System2Node")

RISK_LIMIT = 0.50

def system_2_simulation_node(state: AgentState) -> Dict[str, Any]:
    logger.info("--- [Graph] System 2 Simulation (Rational Fallback) ---")

    plan = state.get("execution_plan_output")
    if not plan:
        return {
            "risk_status": "REJECTED_REVISE",
            "risk_feedback": "System 2: No plan to simulate.",
            "next_step": "execution_analyst"
        }

    # 1. Map Action to Intervention
    # Heuristic parsing of the plan
    # Assumption: plan is a dict with 'steps' or just the dict itself
    action_type = "unknown"
    intervention = {}

    # Extract action from plan (simplified)
    if isinstance(plan, dict):
        # Look for action in steps
        steps = plan.get("steps", [])
        if steps and isinstance(steps, list):
            first_step = steps[0]
            if isinstance(first_step, dict):
                action_type = first_step.get("action", "unknown")
    elif isinstance(plan, str):
         if "block" in plan.lower():
             action_type = "block_transaction"

    # Map to Causal Intervention
    if action_type == "block_transaction":
        intervention = {"Customer_Friction": 0.9} # High Friction
        logger.info("mapped action 'block_transaction' -> Customer_Friction=0.9")
    elif action_type == "approve_transaction":
        intervention = {"Customer_Friction": 0.1} # Low Friction
    else:
        # Default fallback intervention (Medium Friction) if uncertain
        intervention = {"Customer_Friction": 0.5}

    # 2. Build Context
    # In a real app, this comes from a Feature Store or User Profile Service
    # Here we mock/infer based on state or defaults
    context = {
        "Tenure_Years": 5.0, # Default to critical threshold to be safe
        "Transaction_Amount": 1000,
        "Location_Mismatch": 0,
        "Fraud_Risk": 0.5
    }

    # 3. Execute Simulation
    engine = ProductionSCM()
    target_variable = "Churn_Probability"

    risk_score = engine.simulate_intervention(
        context=context,
        intervention=intervention,
        target_variable=target_variable
    )

    logger.info(f"⚖️ System 2 Verification: Risk({target_variable}) = {risk_score:.4f} (Limit: {RISK_LIMIT})")

    # 4. Decision Logic
    if risk_score > RISK_LIMIT:
        feedback = (
            f"System 2 Rational Fallback REJECTED the action '{action_type}'. "
            f"Causal simulation predicts {target_variable} of {risk_score:.2f}, which exceeds limit {RISK_LIMIT}. "
            "Consider alternative actions or human review."
        )
        return {
            "risk_status": "REJECTED_REVISE",
            "risk_feedback": feedback,
            "next_step": "execution_analyst",
            "evaluation_result": {
                "verdict": "REJECTED",
                "reasoning": feedback,
                "simulation_logs": [f"Risk Score: {risk_score}"],
                "policy_check": "UNCERTAIN -> SYSTEM 2 DENY",
                "semantic_check": "N/A"
            }
        }
    else:
        feedback = f"System 2 Rational Fallback APPROVED. Risk {risk_score:.2f} is within limits."
        return {
            "risk_status": "APPROVED",
            "risk_feedback": feedback,
            "next_step": "governed_trader", # Route to Executor
             "evaluation_result": {
                "verdict": "APPROVED",
                "reasoning": feedback,
                "simulation_logs": [f"Risk Score: {risk_score}"],
                "policy_check": "UNCERTAIN -> SYSTEM 2 ALLOW",
                "semantic_check": "N/A"
            }
        }
