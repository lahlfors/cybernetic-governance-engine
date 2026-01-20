import pytest
from src.governance.stpa import UCA, UCAType, HazardType, ConstraintLogic, ProcessModelFlaw
from src.governance.transpiler import PolicyTranspiler
from src.agents.risk_analyst.agent import RiskAssessment, get_risk_analyst_instruction
from src.evaluator_agent.ontology import TradingKnowledgeGraph

def test_stpa_model_instantiation():
    """Test that we can create UCA objects with the new schema."""
    uca = UCA(
        id="UCA-TEST",
        type=UCAType.PROVIDED,
        hazard=HazardType.H_FIN_INSOLVENCY,
        description="Test UCA",
        logic=ConstraintLogic(variable="drawdown", operator=">", threshold="5.0"),
        process_model_flaw=ProcessModelFlaw(
            believed_state="Safe",
            actual_state="Unsafe",
            missing_feedback="Sensor"
        )
    )
    assert uca.id == "UCA-TEST"
    assert uca.type == UCAType.PROVIDED
    assert uca.hazard == HazardType.H_FIN_INSOLVENCY
    assert uca.logic.variable == "drawdown"
    assert uca.process_model_flaw.believed_state == "Safe"

def test_transpiler_stpa_integration():
    """Test that the Transpiler accepts the new UCA model."""
    transpiler = PolicyTranspiler()

    uca = UCA(
        id="UCA-TRANS",
        type=UCAType.PROVIDED,
        hazard=HazardType.H_FIN_LIQUIDITY,
        description="Slippage Risk",
        logic=ConstraintLogic(variable="order_size", operator=">", threshold="0.02 * daily_volume")
    )

    # Generate Python
    py_code = transpiler.generate_nemo_action(uca)
    assert "def check_slippage_risk" in py_code
    assert "Enforces H-FIN-2: Liquidity Trap (Slippage)" in py_code
    assert "0.02" in py_code

    # Generate Rego
    rego_code = transpiler.generate_rego_policy(uca)
    assert "decision = \"DENY\"" in rego_code
    assert "input.amount > (daily_vol * 0.02)" in rego_code

def test_risk_analyst_prompt_update():
    """Verify the prompt has been updated with STPA instructions."""
    prompt = get_risk_analyst_instruction()
    assert "Process Model Flaw" in prompt
    assert "Stopped Too Soon" in prompt
    assert "H-FIN-1" in prompt

def test_evaluator_ontology_integration():
    """Verify that the Red Team ontology uses the new shared UCA model."""
    kg = TradingKnowledgeGraph()
    assert len(kg.ucas) > 0
    first_uca = list(kg.ucas.values())[0]
    assert isinstance(first_uca, UCA)
    assert isinstance(first_uca.type, UCAType)
    assert isinstance(first_uca.hazard, HazardType)
