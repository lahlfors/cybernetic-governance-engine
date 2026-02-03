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
Production Causal Engine (Runtime Kernel)

This module provides the `ProductionSCM` class, which wraps the trained
Structural Causal Model to provide thread-safe intervention capabilities
for the System 2 fallback mechanism.
"""

import logging
import os
import joblib
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

import dowhy.gcm as gcm
from dowhy.gcm import StructuralCausalModel

logger = logging.getLogger("CausalEngine")

class ProductionSCM:
    """
    Singleton wrapper for the production Structural Causal Model.
    """
    _instance = None
    _model: Optional[StructuralCausalModel] = None

    def __new__(cls, model_path: str = "models/prod_scm_v1.pkl"):
        if cls._instance is None:
            cls._instance = super(ProductionSCM, cls).__new__(cls)
            cls._instance._load_model(model_path)
        return cls._instance

    def _load_model(self, model_path: str):
        """Loads the serialized SCM artifact."""
        if os.path.exists(model_path):
            try:
                self._model = joblib.load(model_path)
                logger.info(f"✅ Loaded Production SCM from {model_path}")
            except Exception as e:
                logger.error(f"❌ Failed to load SCM: {e}")
                self._model = None
        else:
            logger.warning(f"⚠️ SCM artifact not found at {model_path}. Engine running in fallback/dummy mode.")
            self._model = None

    def simulate_intervention(
        self,
        context: Dict[str, Any],
        intervention: Dict[str, Any],
        target_variable: str,
        num_samples: int = 50
    ) -> float:
        """
        Executes the 'do-operator' (intervention) on the causal graph.

        Args:
            context: Observed state (e.g., {'Tenure_Years': 5, 'Amount': 1000})
            intervention: The action to test (e.g., {'Customer_Friction': 0.9})
            target_variable: The outcome to measure (e.g., 'Churn_Probability')
            num_samples: Number of Monte Carlo samples for estimation

        Returns:
            The mean predicted value of the target variable (e.g., probability of risk).
        """
        if self._model is None:
            logger.warning("SCM not loaded. Returning high risk (1.0) for safety.")
            return 1.0

        try:
            # 1. Context Mapping & Filtering
            # Only keep keys that exist in the graph nodes
            graph_nodes = self._model.graph.nodes
            filtered_context = {
                k: v for k, v in context.items()
                if k in graph_nodes
            }

            # Convert context to DataFrame (1 row)
            context_df = pd.DataFrame([filtered_context])

            # 2. Define Intervention Function
            # We treat the intervention as a hard assignment
            def intervention_func(x, value):
                return np.full_like(x, value)

            interventions = {}
            for k, v in intervention.items():
                # gcm requires a function for the intervention
                # We use a lambda that returns a constant array of the value
                interventions[k] = lambda x, v=v: intervention_func(x, v)

            # 3. Simulation (Conditioned on Context + Intervention)
            # We use interventional_samples but we ALSO intervene on the context variables.
            # By fixing the context variables (e.g. Tenure=5) via do-operator,
            # we simulate "What happens if a user has Tenure=5 AND we apply Block?".
            # This avoids the complexity/instability of full counterfactual inversion
            # while answering the relevant policy question.

            # Add context variables to interventions
            for k, v in filtered_context.items():
                # Only override if not already in intervention (Intervention takes precedence, though they shouldn't overlap)
                if k not in interventions:
                     interventions[k] = lambda x, v=v: intervention_func(x, v)

            cf_samples = gcm.interventional_samples(
                self._model,
                interventions=interventions,
                num_samples_to_draw=num_samples
            )

            # 4. Result Aggregation
            if target_variable in cf_samples.columns:
                mean_outcome = cf_samples[target_variable].mean()
                return float(mean_outcome)
            else:
                logger.error(f"Target {target_variable} not in output.")
                return 1.0 # Fail Safe

        except Exception as e:
            logger.error(f"Simulation execution failed: {e}")
            return 1.0 # Fail Safe
