# src/causal/engine.py
import joblib
import pandas as pd
import dowhy.gcm as gcm
import networkx as nx
from typing import Dict, Any, Optional
import os

class ProductionSCM:
    """
    The Real Production Engine.
    Wraps a trained DoWhy GCM model to perform real-time interventions.
    """
    def __init__(self, model_path: str = "models/prod_scm_v1.pkl"):
        # Load the pre-trained SCM artifact
        self.model_path = model_path
        if os.path.exists(model_path):
            try:
                self.scm = joblib.load(model_path)
                print(f"--- SCM Loaded from {model_path} ---")
            except Exception as e:
                print(f"!!! Error loading SCM: {e}. Initializing empty graph.")
                self.scm = gcm.StructuralCausalModel(nx.DiGraph())
        else:
            # Fallback for dev/testing if model doesn't exist yet
            print(f"!!! WARNING: Model not found at {model_path}. Creating empty SCM for structure only.")
            self.scm = gcm.StructuralCausalModel(nx.DiGraph())

    def simulate_intervention(self,
                              context: Dict[str, Any],
                              intervention: Dict[str, Any],
                              target_variable: str,
                              num_samples: int = 100) -> float:
        """
        Executes the 'do-operator' using the trained Causal Model.

        Args:
            context: The observed state of the current user (Evidence).
            intervention: The action we want to test (e.g., {'Customer_Friction': 1.0}).
            target_variable: The outcome we care about (e.g., 'Churn_Probability').
        """
        if len(self.scm.graph.nodes) == 0:
             print("!!! SCM is empty. Returning default probability.")
             return 0.5 # Fail-safe

        # 1. Structure the Input Data
        # We start with the specific context of *this* user.
        # This acts as the "Conditioning" set.
        # We need to filter context to only include known nodes to avoid errors
        known_nodes = set(self.scm.graph.nodes)
        filtered_context = {k: v for k, v in context.items() if k in known_nodes}

        # Create a DataFrame with the single observation
        single_row_df = pd.DataFrame([filtered_context])

        # Replicate the row `num_samples` times to get a distribution of outcomes
        # for this specific user context.
        current_state_df = pd.concat([single_row_df] * num_samples, ignore_index=True)

        # 2. Perform the Intervention
        # We ask DoWhy: "Given this user state, if we force the intervention, what happens?"

        # We define the intervention dictionary for DoWhy
        # lambda x: x * 0 + value forces the variable to the value (breaking the edge)
        intervention_func = {}
        for k, v in intervention.items():
            # Use a default argument in lambda to capture the value of v immediately
            intervention_func[k] = lambda x, val=v: x * 0 + val

        # 3. Run Simulation
        # This draws samples from the mutilated graph P(Y | do(X))
        try:
            # Note: observed_data already implies the number of samples if provided.
            # We can't pass both if observed_data is used to condition on specific instances.

            samples = gcm.interventional_samples(
                self.scm,
                interventions=intervention_func,
                observed_data=current_state_df # Condition on current state
            )

            # 4. Aggregation
            # Return the mean expected probability
            if target_variable in samples.columns:
                result = samples[target_variable].mean()
                return float(result)
            else:
                print(f"!!! Target variable {target_variable} not in samples.")
                return 0.5

        except Exception as e:
            print(f"!!! Simulation failed: {e}")
            return 0.5

# Singleton Instance
# In a real app, you might lazily load this.
scm_engine = ProductionSCM()
