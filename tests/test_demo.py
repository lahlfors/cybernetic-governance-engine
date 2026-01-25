from unittest.mock import MagicMock, patch

import pytest

from src.demo.pipeline_manager import submit_vertex_pipeline
from src.demo.state import DemoState, demo_state


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
    assert clean_state.pipeline_status["mode"] == "vertex"
    assert clean_state.pipeline_status["dashboard_url"] == "http://google.com/dashboard"
    assert clean_state.latest_trace_id is not None
