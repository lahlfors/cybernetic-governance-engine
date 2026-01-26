import pytest
import os
import shutil
from src.causal.engine import ProductionSCM

@pytest.fixture(scope="module")
def causal_model_artifact():
    # Ensure the model exists (it should from the manual run, but let's be safe)
    if not os.path.exists("models/prod_scm_v1.pkl"):
        pytest.skip("Causal model artifact not found. Run scripts/train_causal_model.py first.")
    return "models/prod_scm_v1.pkl"

def test_production_scm_singleton(causal_model_artifact):
    engine1 = ProductionSCM()
    engine2 = ProductionSCM()
    assert engine1 is engine2
    assert engine1.scm is not None

def test_simulate_intervention_valid(causal_model_artifact):
    engine = ProductionSCM()

    context = {
        "Transaction_Amount": 1000,
        "Location_Mismatch": 0,
        "Tenure_Years": 5.0,
        "Fraud_Risk": 0.1
    }

    intervention = {"Customer_Friction": 0.9}

    result = engine.simulate_intervention(
        context=context,
        intervention=intervention,
        target="Churn_Probability",
        samples=10
    )

    assert isinstance(result, float)
    assert 0.0 <= result <= 1.0

def test_simulate_intervention_missing_target(causal_model_artifact):
    engine = ProductionSCM()
    result = engine.simulate_intervention(
        context={},
        intervention={},
        target="NonExistentVariable",
        samples=10
    )
    assert result == 0.0 # Default safe
