import logging
import os
import pickle
from typing import Any, Dict, Optional

import dowhy.gcm as gcm
import networkx as nx
import pandas as pd
import numpy as np

logger = logging.getLogger("CausalEngine")

class ProductionSCM:
    """
    Runtime kernel for the Causal Engine.
    Wraps dowhy.gcm to provide causal inference capabilities.
    """
    _instance = None

    def __new__(cls, model_path: str = "models/prod_scm_v1.pkl"):
        if cls._instance is None:
            cls._instance = super(ProductionSCM, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_path: str = "models/prod_scm_v1.pkl"):
        if self._initialized:
            return

        self.model_path = model_path
        self.scm = self._load_model()
        self._initialized = True

    def _load_model(self) -> Optional[gcm.StructuralCausalModel]:
        """Loads the serialized SCM artifact."""
        if not os.path.exists(self.model_path):
            logger.warning(f"⚠️ Causal Model artifact not found at {self.model_path}. Running in degradation mode (Empty SCM).")
            # Return an empty SCM or None to indicate unavailability
            return None

        try:
            with open(self.model_path, "rb") as f:
                scm = pickle.load(f)
            logger.info(f"✅ Loaded Causal Model from {self.model_path}")
            return scm
        except Exception as e:
            logger.error(f"❌ Failed to load Causal Model: {e}")
            return None

    def simulate_intervention(
        self,
        context: Dict[str, Any],
        intervention: Dict[str, Any],
        target: str,
        samples: int = 50
    ) -> float:
        """
        Executes the "do-operator" to estimate the probability of a target outcome.

        Args:
            context: The current state/context (observed variables).
            intervention: Dictionary of variables to intervene on and their values.
            target: The target variable to measure (e.g., 'Churn_Probability').
            samples: Number of Monte Carlo samples to draw.

        Returns:
            The mean value of the target variable under intervention.
        """
        if self.scm is None:
            logger.warning("Attempted simulation with no loaded SCM. Returning 0.0 safe default.")
            return 0.0

        try:
            # 1. Context Mapping: Filter context to match graph nodes
            # We only care about variables that exist in the graph
            graph_nodes = self.scm.graph.nodes
            filtered_context = {k: v for k, v in context.items() if k in graph_nodes}

            # 2. Convert to DataFrame for DoWhy
            # DoWhy expects a DataFrame for conditioning (observations)
            # We create a single-row DataFrame
            observed_data = pd.DataFrame([filtered_context])

            # 3. Define Intervention
            # GCM supports atomic values for interventions.
            # We treat the context variables as "fixed" interventions (Conditioning by Intervention).

            full_intervention = {}

            def make_intervention_func(value):
                def wrapper(x):
                    # Handle integer (num_samples for root nodes in some GCM versions)
                    if isinstance(x, int):
                         return np.full(x, value)

                    # Handle numpy array or scalar
                    if hasattr(x, 'shape'):
                         if x.ndim == 0:
                             # Input is scalar (e.g. single sample iteration), return scalar
                             return np.array(value, dtype=x.dtype)
                         # Input is vector, return vector of same size
                         return np.full(x.shape, value)

                    # Handle empty tuple (Root nodes with no parents often passed as empty tuple)
                    if isinstance(x, tuple) and len(x) == 0:
                         # If it's a tuple, we assume we need to return 'samples' size
                         # because we can't infer size from tuple.
                         return np.full(samples, value)

                    # Fallback
                    return np.array([value])
                return wrapper

            # Add explicit interventions
            for k, v in intervention.items():
                if k in graph_nodes:
                     # We wrap in a lambda because 'int' is not callable for intermediate nodes in some versions
                     full_intervention[k] = make_intervention_func(v)

            # Add context as interventions (do(Context))
            for k, v in filtered_context.items():
                if k not in full_intervention:
                    full_intervention[k] = make_intervention_func(v)

            # 4. Execute Simulation
            # We use conditional sampling via intervention.
            # This asks: "If we set inputs to Context and Action, what is the distribution of Target?"

            samples_df = gcm.interventional_samples(
                self.scm,
                interventions=full_intervention,
                num_samples_to_draw=samples
            )

            # 5. Calculate Result
            if target in samples_df.columns:
                mean_result = samples_df[target].mean()
                return float(mean_result)
            else:
                logger.error(f"Target variable {target} not found in simulation output.")
                return 0.0

        except Exception as e:
            logger.error(f"Simulation failed: {e}")
            return 0.0
