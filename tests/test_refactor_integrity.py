import pytest
from unittest.mock import MagicMock, patch
import os
import sys

# --- Pre-Import Mocks for Missing Dependencies ---
# We must mock these BEFORE importing src.* because they are not installed in the test env.
mock_google = MagicMock()
mock_adk = MagicMock()
mock_cloud = MagicMock()

# Structure the mock hierarchy
mock_google.adk = mock_adk
mock_google.cloud = mock_cloud

# Mock specific classes used in imports
mock_adk.Agent = MagicMock
mock_adk.tools = MagicMock()

# Inject into sys.modules
sys.modules["google"] = mock_google
sys.modules["google.adk"] = mock_adk
sys.modules["google.adk.tools"] = mock_adk.tools
sys.modules["google.cloud"] = mock_cloud
sys.modules["google.cloud.storage"] = MagicMock()
sys.modules["google.genai"] = MagicMock()
sys.modules["langchain_google_genai"] = MagicMock()

# Now we can import our code
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.agents.risk_analyst.agent import get_risk_analyst_instruction, ProposedUCA, ConstraintLogic
from src.governance.transpiler import PolicyTranspiler
from src.governance.policy_loader import PolicyLoader

# --- Mocks ---

@pytest.fixture
def mock_gcs_loader():
    # We patch the import location within policy_loader
    with patch("src.governance.policy_loader.storage.Client") as mock_client:
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        # Setup mock behavior
        mock_client.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        # Mock STAMP YAML content
        mock_blob.download_as_text.return_value = """
hazards:
  - hazard: "Test Hazard"
    description: "Test Description"
    logic:
      variable: "test_var"
      operator: ">"
      threshold: "10"
"""
        yield mock_client

@pytest.fixture
def mock_judge_agent():
    with patch("src.governance.transpiler.JudgeAgent") as mock_class:
        mock_instance = mock_class.return_value
        yield mock_instance

# --- Tests ---

def test_policy_loader_uses_gcs(mock_gcs_loader):
    """Verify PolicyLoader attempts to fetch from GCS."""
    loader = PolicyLoader(bucket_name="test-bucket")
    hazards = loader.load_stamp_hazards("spec.yaml")

    assert len(hazards) == 1
    assert hazards[0]["hazard"] == "Test Hazard"
    # Verify GCS client calls
    mock_gcs_loader.return_value.bucket.assert_called_with("test-bucket")

def test_risk_analyst_uses_dynamic_hazards(mock_gcs_loader):
    """Verify Risk Analyst prompt is constructed dynamically."""
    with patch.object(PolicyLoader, 'load_stamp_hazards') as mock_load:
         mock_load.return_value = [{
             "hazard": "Dynamic Hazard 1",
             "description": "Dynamic Desc",
             "logic": {}
         }]

         instruction = get_risk_analyst_instruction()

         assert "Dynamic Hazard 1" in instruction
         assert "Dynamic Desc" in instruction

def test_transpiler_invokes_judge(mock_judge_agent):
    """Verify Transpiler calls JudgeAgent.verify."""
    transpiler = PolicyTranspiler()
    # Ensure LLM is mocked or disabled for this unit test to avoid network calls
    transpiler.use_llm = True
    transpiler._generate_with_llm = MagicMock(return_value="package finance\ndecision = \"DENY\"")

    mock_judge_agent.verify.return_value = True

    uca = ProposedUCA(
        category="Test",
        hazard="Test Hazard",
        description="Desc",
        constraint_logic=ConstraintLogic(variable="x", operator=">", threshold="1")
    )

    rego = transpiler.generate_rego_policy(uca)

    assert "package finance" in rego
    mock_judge_agent.verify.assert_called_once()

def test_transpiler_blocks_on_judge_rejection(mock_judge_agent):
    """Verify Transpiler rejects code if Judge returns False."""
    transpiler = PolicyTranspiler()
    transpiler.use_llm = True
    transpiler._generate_with_llm = MagicMock(return_value="BAD CODE")

    # Judge rejects
    mock_judge_agent.verify.return_value = False

    uca = ProposedUCA(
        category="Test",
        hazard="Test Hazard",
        description="Desc",
        constraint_logic=ConstraintLogic(variable="x", operator=">", threshold="1")
    )

    rego = transpiler.generate_rego_policy(uca)

    # Should fall back to template or return different code
    # Our implementation logs a warning and falls back to template
    assert "BAD CODE" not in rego
    # It should effectively be the template fallback
    assert "decision = \"DENY\"" in rego
