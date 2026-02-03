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
Offline Training Pipeline for Causal Engine.

This script constructs the "Physics" of the domain model, generates synthetic data
(bootstrapping), trains the Structural Causal Model (SCM), and serializes it
for production use.
"""

import logging
import joblib
import networkx as nx
import pandas as pd
import numpy as np
from typing import Tuple

import dowhy.gcm as gcm
from dowhy.gcm.ml import create_hist_gradient_boost_regressor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TrainCausalModel")

MODEL_PATH = "models/prod_scm_v1.pkl"
NUM_SAMPLES = 5000

def create_graph() -> nx.DiGraph:
    """Defines the causal DAG."""
    dag = nx.DiGraph()

    # Nodes
    dag.add_nodes_from([
        "Transaction_Amount",
        "Location_Mismatch", # Binary: 0 or 1
        "Fraud_Risk",        # Probability 0-1
        "Tenure_Years",      # Years
        "Customer_Friction", # Interaction Intensity 0-1 (Block is High)
        "Churn_Probability"  # Probability 0-1
    ])

    # Edges
    dag.add_edges_from([
        ("Transaction_Amount", "Fraud_Risk"),
        ("Location_Mismatch", "Fraud_Risk"),
        ("Fraud_Risk", "Customer_Friction"),     # System Policy: Higher risk -> Higher friction
        ("Customer_Friction", "Churn_Probability"),
        ("Tenure_Years", "Churn_Probability"),   # Long tenure -> Lower churn, but sensitive to friction
    ])

    return dag

def generate_synthetic_data(num_samples: int) -> pd.DataFrame:
    """
    Generates synthetic training data based on domain assumptions.
    Ideally, this is replaced by real logs + Causal Discovery.
    """
    np.random.seed(42)

    # Root Nodes
    amount = np.random.exponential(scale=1000, size=num_samples)
    location_mismatch = np.random.binomial(n=1, p=0.1, size=num_samples)
    tenure = np.random.uniform(0, 10, size=num_samples)

    # Mechanisms (Functional Relationships)

    # Fraud Risk: Increases with Amount and Location Mismatch
    # Sigmoid function
    z_fraud = (amount / 2000) + (location_mismatch * 2) - 2 + np.random.normal(0, 0.2, size=num_samples)
    fraud_risk = 1 / (1 + np.exp(-z_fraud))

    # Customer Friction: System Policy (noisy)
    # If Risk > 0.7, Friction is High (Block ~ 0.9). Else Low (Allow ~ 0.1)
    friction = np.where(fraud_risk > 0.6,
                        np.random.normal(0.9, 0.05, size=num_samples),
                        np.random.normal(0.1, 0.05, size=num_samples))
    friction = np.clip(friction, 0, 1)

    # Churn Probability: The "Insult Effect"
    # Base churn is low.
    # High Friction increases churn.
    # High Tenure *reduces* base churn, BUT...
    # High Tenure + High Friction = "Insult" (Massive Churn Spike)

    base_churn = 0.05
    tenure_factor = -0.005 * tenure # Tenure reduces churn slightly
    friction_factor = 0.3 * friction

    # Interaction: Insult
    # If Tenure > 5 and Friction > 0.8 => +0.5 Churn Risk
    insult_factor = (tenure > 5).astype(float) * (friction > 0.8).astype(float) * 0.6

    z_churn = base_churn + tenure_factor + friction_factor + insult_factor + np.random.normal(0, 0.05, size=num_samples)
    churn_prob = np.clip(z_churn, 0, 1)

    df = pd.DataFrame({
        "Transaction_Amount": amount,
        "Location_Mismatch": location_mismatch,
        "Fraud_Risk": fraud_risk,
        "Tenure_Years": tenure,
        "Customer_Friction": friction,
        "Churn_Probability": churn_prob
    })

    return df

def train_model() -> None:
    logger.info("构建 Building Causal Graph...")
    dag = create_graph()
    scm = gcm.StructuralCausalModel(dag)

    logger.info("🎲 Generating Synthetic Data...")
    data = generate_synthetic_data(NUM_SAMPLES)

    logger.info("⚙️  Assigning Causal Mechanisms...")
    # Auto-assign for simple nodes
    gcm.auto.assign_causal_mechanisms(scm, data)

    # Override Churn_Probability with Non-Linear Model to capture the "Insult Effect"
    # We use a GBR wrapped in an Additive Noise Model
    # Note: ANM expects Y = f(Parents) + N
    scm.set_causal_mechanism('Churn_Probability',
                             gcm.AdditiveNoiseModel(create_hist_gradient_boost_regressor()))

    logger.info("🧠 Training SCM...")
    gcm.fit(scm, data)

    logger.info(f"💾 Saving model to {MODEL_PATH}...")
    joblib.dump(scm, MODEL_PATH)
    logger.info("✅ Done.")

if __name__ == "__main__":
    train_model()
