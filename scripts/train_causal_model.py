import logging
import os
import pickle
import numpy as np
import pandas as pd
import networkx as nx
import dowhy.gcm as gcm
from scipy.stats import norm
from sklearn.ensemble import HistGradientBoostingRegressor

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CausalTrainer")

OUTPUT_PATH = "models/prod_scm_v1.pkl"
SAMPLES = 2000

def create_causal_graph() -> nx.DiGraph:
    """Defines the DAG structure."""
    causal_graph = nx.DiGraph([
        ("Transaction_Amount", "Fraud_Risk"),
        ("Location_Mismatch", "Fraud_Risk"),
        ("Fraud_Risk", "Customer_Friction"),
        ("Tenure_Years", "Churn_Probability"),
        ("Customer_Friction", "Churn_Probability")
    ])
    return causal_graph

def generate_synthetic_data(num_samples: int) -> pd.DataFrame:
    """Generates bootstrap training data based on domain assumptions."""
    logger.info(f"Generating {num_samples} synthetic samples...")

    # 1. Root Nodes
    data = pd.DataFrame()
    data["Transaction_Amount"] = np.random.exponential(scale=1000, size=num_samples) # Avg $1000
    data["Location_Mismatch"] = np.random.choice([0, 1], size=num_samples, p=[0.8, 0.2]) # 20% mismatch
    data["Tenure_Years"] = np.random.uniform(0, 20, size=num_samples) # 0 to 20 years

    # 2. Fraud Risk (Amount + Location)
    # High Amount + Mismatch = High Risk
    # Normalize amount for easier math
    norm_amount = data["Transaction_Amount"] / 5000
    noise_fraud = np.random.normal(0, 0.1, size=num_samples)

    data["Fraud_Risk"] = (
        0.3 * norm_amount +
        0.6 * data["Location_Mismatch"] +
        0.1 * (norm_amount * data["Location_Mismatch"]) + # Interaction
        noise_fraud
    )
    # Clip to [0, 1]
    data["Fraud_Risk"] = data["Fraud_Risk"].clip(0, 1)

    # 3. Customer Friction (Driven by Fraud Risk + Policy Interventions)
    # In training data, Friction is highly correlated with Fraud Risk (System 1 logic)
    noise_friction = np.random.normal(0, 0.05, size=num_samples)
    data["Customer_Friction"] = data["Fraud_Risk"] + noise_friction
    data["Customer_Friction"] = data["Customer_Friction"].clip(0, 1)

    # 4. Churn Probability (Tenure vs Friction)
    # "Insult Effect": High Friction causes Churn, but High Tenure mitigates it...
    # UNTIL a breaking point where loyal customers feel betrayed.
    # Logic:
    # - Base churn is low.
    # - Friction increases churn.
    # - Tenure decreases churn.
    # - Interaction: If Friction > 0.8 AND Tenure > 5, Churn SPIKES (The Insult)

    def calculate_churn(row):
        base_churn = 0.05
        friction_impact = 0.5 * row["Customer_Friction"]
        tenure_impact = -0.02 * row["Tenure_Years"]

        # The Insult Effect (Non-linear)
        insult = 0.0
        if row["Customer_Friction"] > 0.7 and row["Tenure_Years"] > 7.0:
            insult = 0.4 # Massive spike

        prob = base_churn + friction_impact + tenure_impact + insult
        return np.clip(prob, 0, 1)

    data["Churn_Probability"] = data.apply(calculate_churn, axis=1)

    # Add some random noise to churn
    data["Churn_Probability"] += np.random.normal(0, 0.02, size=num_samples)
    data["Churn_Probability"] = data["Churn_Probability"].clip(0, 1)

    return data

def train_and_save_model():
    # 1. Setup
    graph = create_causal_graph()
    scm = gcm.StructuralCausalModel(graph)
    data = generate_synthetic_data(SAMPLES)

    # 2. Assign Mechanisms
    # Auto-assign for simple nodes
    gcm.auto.assign_causal_mechanisms(scm, data)

    # Explicit override for Churn_Probability (The critical non-linear node)
    # Using Additive Noise Model with Histogram Gradient Boosting
    logger.info("Assigning custom non-linear mechanism for Churn_Probability...")
    scm.set_causal_mechanism(
        'Churn_Probability',
        gcm.AdditiveNoiseModel(gcm.ml.create_hist_gradient_boost_regressor())
    )

    # Explicit override for Customer_Friction to ensure it captures complex policy logic
    scm.set_causal_mechanism(
        'Customer_Friction',
        gcm.AdditiveNoiseModel(gcm.ml.create_hist_gradient_boost_regressor())
    )

    # 3. Fit Model
    logger.info("Fitting Causal Model (this may take a moment)...")
    gcm.fit(scm, data)
    logger.info("✅ Model Fitting Complete.")

    # 4. Serialize
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "wb") as f:
        pickle.dump(scm, f)

    logger.info(f"✅ SCM Artifact saved to {OUTPUT_PATH}")

if __name__ == "__main__":
    train_and_save_model()
