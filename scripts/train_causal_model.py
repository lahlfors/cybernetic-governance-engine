# scripts/train_causal_model.py
import networkx as nx
import pandas as pd
import numpy as np
import dowhy.gcm as gcm
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
import joblib
import os

def generate_synthetic_data(n_samples=1000):
    print("--- Generating Synthetic Data ---")
    np.random.seed(42)

    # Root Nodes
    transaction_amount = np.random.normal(loc=100, scale=50, size=n_samples)
    transaction_amount = np.maximum(transaction_amount, 0) # Non-negative

    location_mismatch = np.random.binomial(n=1, p=0.1, size=n_samples) # 10% mismatch

    tenure_years = np.random.uniform(0, 10, size=n_samples)

    # Intermediate Nodes
    # Fraud Risk depends on Amount and Location
    # High amount + Location mismatch -> High Fraud Risk
    fraud_risk_latent = (transaction_amount / 200) + (location_mismatch * 2) + np.random.normal(0, 0.1, size=n_samples)
    fraud_risk = 1 / (1 + np.exp(-fraud_risk_latent)) # Sigmoid to keep 0-1

    # Customer Friction depends on Fraud Risk (Blocking high risk causes friction)
    # But let's say sometimes we block legitimate users too (False Positives)
    # Modeled as continuous score 0-1
    customer_friction = fraud_risk * 0.8 + np.random.normal(0, 0.05, size=n_samples)
    customer_friction = np.clip(customer_friction, 0, 1)

    # Churn Probability depends on Tenure and Friction
    # - Low Friction: Tenure reduces churn (Loyalty)
    # - High Friction (Block): Tenure INCREASES churn sensitivity (The "Insult" Effect)

    # Interaction: Friction * Tenure
    # If Friction is low (0), Churn decreases with Tenure (-0.5 * Tenure)
    # If Friction is high (1), Churn increases with Tenure (+0.5 * Tenure) because they get angry

    interaction = (customer_friction - 0.2) * tenure_years * 0.5

    churn_prob_latent = (customer_friction * 2) + interaction - 2.0 + np.random.normal(0, 0.1, size=n_samples)
    churn_probability = 1 / (1 + np.exp(-churn_prob_latent)) # Sigmoid

    df = pd.DataFrame({
        'Transaction_Amount': transaction_amount,
        'Location_Mismatch': location_mismatch,
        'Tenure_Years': tenure_years,
        'Fraud_Risk': fraud_risk,
        'Customer_Friction': customer_friction,
        'Churn_Probability': churn_probability
    })

    return df

def train_and_save_scm():
    print("--- [Offline] Starting Causal Model Training ---")

    # 0. Ensure models directory exists
    os.makedirs("models", exist_ok=True)

    # 1. Define the Graph Structure (Domain Knowledge + Discovery)
    # This represents the "Physics" of your banking system.
    causal_graph = nx.DiGraph([
        ("Transaction_Amount", "Fraud_Risk"),
        ("Location_Mismatch", "Fraud_Risk"),
        ("Fraud_Risk", "Customer_Friction"), # Blocking high risk causes friction
        ("Tenure_Years", "Churn_Probability"),
        ("Customer_Friction", "Churn_Probability")
    ])

    # 2. Create the SCM Object
    scm = gcm.StructuralCausalModel(causal_graph)

    # 3. Assign Mechanisms (The "Muscles")
    # Instead of manual math, we use actual ML models to learn relationships.

    # Root nodes: Modeled as empirical distributions
    # We don't have data yet, so we will assign auto mechanisms AFTER loading data usually,
    # but here we define types first. gcm.auto.assign_causal_mechanisms simplifies this.
    # However, for manual control let's do explicit assignment where we can,
    # or rely on auto assignment on the data.

    # Let's use auto-assignment which infers from data for root nodes
    # For downstream nodes, we can be specific.

    # We will use auto assignment for everything to keep it robust for this demo,
    # but override specific functional relationships if needed.
    # Ideally, we define the mechanism type.

    # Note: gcm.auto.assign_causal_mechanisms(scm, data) is the standard way.

    # 4. Load Data
    data = generate_synthetic_data(5000)

    print("--- Assigning Mechanisms... ---")
    gcm.auto.assign_causal_mechanisms(scm, data)

    # Optional: Explicitly set non-linear regressors for complex relationships if auto picks linear
    # But auto usually picks a good default. Let's force non-linear for Friction/Churn as per user request
    scm.set_causal_mechanism('Customer_Friction', gcm.AdditiveNoiseModel(gcm.ml.create_hist_gradient_boost_regressor()))
    scm.set_causal_mechanism('Churn_Probability', gcm.AdditiveNoiseModel(gcm.ml.create_hist_gradient_boost_regressor()))


    # 5. Fit the Model (Training)
    print("--- Fitting Mechanisms... ---")
    gcm.fit(scm, data)

    # 6. Save the Artifact
    output_path = "models/prod_scm_v1.pkl"
    print(f"--- Saving Production Artifact to {output_path}... ---")
    joblib.dump(scm, output_path)
    print("--- Done. ---")

if __name__ == "__main__":
    train_and_save_scm()
