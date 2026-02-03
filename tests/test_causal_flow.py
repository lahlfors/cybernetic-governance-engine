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

import pytest
import asyncio
from unittest.mock import MagicMock, patch

from src.causal.engine import ProductionSCM
from src.governed_financial_advisor.graph.nodes.system_2_simulation_node import system_2_simulation_node
from src.gateway.core.policy import OPAClient

@pytest.fixture
def mock_scm():
    with patch("src.causal.engine.joblib.load") as mock_load:
        # Mock the SCM object
        mock_model = MagicMock()
        mock_model.graph.nodes = ["Tenure_Years", "Transaction_Amount", "Location_Mismatch", "Fraud_Risk", "Customer_Friction", "Churn_Probability"]
        mock_load.return_value = mock_model

        # Reset Singleton
        ProductionSCM._instance = None

        yield mock_model

def test_causal_engine_load(mock_scm):
    engine = ProductionSCM()
    assert engine._model is not None

def test_system_2_node_deny(mock_scm):
    # Setup Engine Mock to return HIGH RISK
    with patch("src.causal.engine.gcm.interventional_samples") as mock_samples:
        import pandas as pd
        # Return dataframe with high churn
        mock_samples.return_value = pd.DataFrame({"Churn_Probability": [0.8, 0.9]})

        state = {
            "execution_plan_output": {"steps": [{"action": "block_transaction"}]},
            "user_id": "test_user"
        }

        result = system_2_simulation_node(state)

        assert result["risk_status"] == "REJECTED_REVISE"
        assert result["next_step"] == "execution_analyst"
        assert "System 2 Rational Fallback REJECTED" in result["risk_feedback"]

def test_system_2_node_allow(mock_scm):
    # Setup Engine Mock to return LOW RISK
    with patch("src.causal.engine.gcm.interventional_samples") as mock_samples:
        import pandas as pd
        # Return dataframe with low churn
        mock_samples.return_value = pd.DataFrame({"Churn_Probability": [0.1, 0.2]})

        state = {
            "execution_plan_output": {"steps": [{"action": "block_transaction"}]},
            "user_id": "test_user"
        }

        result = system_2_simulation_node(state)

        assert result["risk_status"] == "APPROVED"
        assert result["next_step"] == "governed_trader"
        assert "System 2 Rational Fallback APPROVED" in result["risk_feedback"]

@pytest.mark.asyncio
async def test_opa_uncertainty_trigger():
    client = OPAClient()
    # Mock Can Execute
    client.cb.can_execute = MagicMock(return_value=True)

    result = await client.evaluate_policy({"action": "test_uncertainty"})
    assert result == "UNCERTAIN"
