import logging
import sys
import os

# Add src to path to import engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
from src.causal.engine import ProductionSCM

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PolicyInduction")

OUTPUT_POLICY_FILE = "policies/generated_causal_rules.rego"
RISK_THRESHOLD = 0.45

def discover_safety_boundaries():
    """
    Scans the causal space to find where interventions become unsafe.
    Focus: Blocking users with high tenure.
    """
    logger.info("🔍 Starting Policy Induction...")

    engine = ProductionSCM()
    if engine.scm is None:
        logger.error("❌ Causal Engine not initialized. Run training script first.")
        return

    # 1. Define Search Space
    # We test Tenure from 0 to 15 years
    tenure_values = [i * 0.5 for i in range(31)] # 0, 0.5, ... 15.0

    unsafe_boundary = None

    # Base Context (Average user)
    base_context = {
        "Transaction_Amount": 1000,
        "Location_Mismatch": 0,
        "Fraud_Risk": 0.1, # Low risk initially
    }

    # 2. Simulation Loop
    for tenure in tenure_values:
        # Update context
        context = base_context.copy()
        context["Tenure_Years"] = tenure

        # Apply Intervention: BLOCK the user (High Friction)
        intervention = {"Customer_Friction": 0.9}

        # Simulate
        churn_risk = engine.simulate_intervention(
            context=context,
            intervention=intervention,
            target="Churn_Probability",
            samples=50
        )

        logger.info(f"Scenario [Tenure={tenure}y, Action=BLOCK] -> Churn Risk: {churn_risk:.2f}")

        if churn_risk > RISK_THRESHOLD:
            logger.warning(f"⚠️ Safety Violation Discovered at Tenure={tenure}y (Risk {churn_risk:.2f} > {RISK_THRESHOLD})")
            unsafe_boundary = tenure
            break # Found the boundary (monotonic assumption)

    # 3. Generate Policy
    if unsafe_boundary is not None:
        logger.info(f"🛑 Boundary Identified: Tenure >= {unsafe_boundary}y")
        generate_rego_policy(unsafe_boundary)
    else:
        logger.info("✅ No unsafe boundaries discovered in the search space.")

def generate_rego_policy(tenure_threshold: float):
    """Writes the discovered boundary as a Rego rule."""
    rego_content = f"""package policies.causal_generated

# METADATA
# title: Causal Safety Constraints
# description: Automatically induced from Causal Engine simulations.
# generated_by: scripts/causal_policy_induction.py
# timestamp: {pd.Timestamp.now().isoformat()}

# Default: Allow unless unsafe
default allow = true

# Constraint: Do not block high-tenure customers due to high churn risk (Insult Effect)
deny[msg] {{
    input.action == "block_transaction"
    input.user.tenure_years >= {tenure_threshold}
    msg := sprintf("CAUSAL SAFETY VIOLATION: Blocking users with tenure >= %.1f years causes unacceptable churn risk.", [{tenure_threshold}])
}}
"""
    # Note: Rego might need explicit input structure matching.
    # Assuming input.user.tenure_years is available.

    os.makedirs(os.path.dirname(OUTPUT_POLICY_FILE), exist_ok=True)
    with open(OUTPUT_POLICY_FILE, "w") as f:
        f.write(rego_content)

    logger.info(f"✅ Policy written to {OUTPUT_POLICY_FILE}")

if __name__ == "__main__":
    discover_safety_boundaries()
