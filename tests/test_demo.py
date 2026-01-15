import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.demo.state import demo_state, DemoState
from src.demo.pipeline_manager import run_discovery_locally, submit_vertex_pipeline
from src.agents.risk_analyst.agent import ProposedUCA, ConstraintLogic, RiskAssessment

@pytest.fixture
def clean_state():
    demo_state.reset()
    return demo_state

@pytest.mark.asyncio
async def test_demo_state_singleton():
    s1 = DemoState()
    s2 = DemoState()
    assert s1 is s2
    s1.simulated_latency = 100.0
    assert s2.simulated_latency == 100.0

@pytest.mark.asyncio
@patch("src.demo.pipeline_manager.risk_analyst_agent")
@patch("src.demo.pipeline_manager.transpiler")
async def test_run_discovery_locally_success(mock_transpiler, mock_agent, clean_state):
    # Setup Mock Agent Response
    mock_uca = ProposedUCA(
        category="Wrong Timing",
        hazard="H-2",
        description="Latency Risk",
        constraint_logic=ConstraintLogic(variable="latency", operator=">", threshold="200", condition="order_type=='MARKET'")
    )
    mock_response = RiskAssessment(
        risk_level="High",
        identified_ucas=[mock_uca],
        analysis_text="Risk found."
    )
    mock_agent.invoke = AsyncMock(return_value=mock_response)

    # Setup Transpiler
    mock_transpiler.transpile_policy.return_value = "def check_latency(): return False"

    # Run
    await run_discovery_locally("My Strategy")

    # Verify State
    assert clean_state.pipeline_status["status"] == "completed"
    assert clean_state.pipeline_status["mode"] == "local"
    assert "def check_latency" in clean_state.latest_generated_rules
    assert clean_state.latest_trace_id is not None

@pytest.mark.asyncio
@patch("src.demo.pipeline_manager.risk_analyst_agent")
async def test_run_discovery_locally_failure(mock_agent, clean_state):
    # Setup Mock Failure
    mock_agent.invoke = AsyncMock(side_effect=Exception("Agent Error"))

    # Run
    with pytest.raises(Exception):
        await run_discovery_locally("My Strategy")

    # Verify Error State
    assert clean_state.pipeline_status["status"] == "error"
    assert "Agent Error" in clean_state.pipeline_status["message"]

@pytest.mark.asyncio
@patch("src.demo.pipeline_manager.aiplatform")
@patch("src.demo.pipeline_manager.compiler")
async def test_submit_vertex_pipeline(mock_compiler, mock_aiplatform, clean_state):
    # Mock Vertex AI
    mock_job = MagicMock()
    mock_job._dashboard_uri.return_value = "http://google.com/dashboard"
    mock_aiplatform.PipelineJob.return_value = mock_job

    await submit_vertex_pipeline("My Strategy")

    # Verify
    mock_compiler.Compiler().compile.assert_called()
    mock_aiplatform.init.assert_called()
    mock_job.submit.assert_called()

    assert clean_state.pipeline_status["status"] == "submitted"
    assert clean_state.pipeline_status["dashboard_url"] == "http://google.com/dashboard"
