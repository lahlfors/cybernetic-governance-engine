import os
import pytest
from unittest.mock import patch, MagicMock
from src.governed_financial_advisor.infrastructure.config_manager import ConfigManager # Import Class

@pytest.fixture
def mock_gsm_client():
    # Patch the _gsm_client property or the method that creates it
    # Since _gsm_client is created on first use, we can patch SecretManagerServiceClient
    with patch("google.cloud.secretmanager.SecretManagerServiceClient") as MockClient:
        client_instance = MockClient.return_value
        # Mock successful response
        client_instance.access_secret_version.return_value.payload.data.decode.return_value = "secret-value-from-gsm"
        yield client_instance

@pytest.fixture
def config_manager(mock_gsm_client):
    # We need a fresh instance for each test to pick up environment changes?
    # Actually, ConfigManager.__init__ reads ENV and PROJECT_ID.
    # So if we patch os.environ in a fixture *before* instantiating, it should work.
    # But global instance in module is already instantiated.
    # So we should instantiate a new one inside tests or fixture.
    return ConfigManager()

@pytest.fixture
def production_env():
    # Simulate Production Env
    with patch.dict(os.environ, {"ENV": "production", "GOOGLE_CLOUD_PROJECT": "test-project"}):
        if "TEST_API_KEY" in os.environ:
            del os.environ["TEST_API_KEY"]
        yield

def test_get_from_env_var():
    # 1. Test Env Var Priority
    with patch.dict(os.environ, {"TEST_KEY": "env-value"}):
        cm = ConfigManager() # Fresh instance
        val = cm.get("TEST_KEY")
        assert val == "env-value"

def test_get_from_gsm_fallback(production_env, mock_gsm_client):
    # 2. Test GSM Fallback (when Env Var is missing)
    # We must instantiate AFTER patching env
    cm = ConfigManager()

    val = cm.get("TEST_GSM_KEY")

    assert val == "secret-value-from-gsm"

    # Verify the correct path was called (auto-kebab conversion)
    expected_name = "projects/test-project/secrets/test-gsm-key/versions/latest"
    mock_gsm_client.access_secret_version.assert_called_with(request={"name": expected_name})

def test_get_from_gsm_explicit_id(production_env, mock_gsm_client):
    # 3. Test Explicit Secret ID
    cm = ConfigManager()
    val = cm.get("TEST_KEY_2", secret_id="custom-secret-id")

    assert val == "secret-value-from-gsm"

    expected_name = "projects/test-project/secrets/custom-secret-id/versions/latest"
    mock_gsm_client.access_secret_version.assert_called_with(request={"name": expected_name})

def test_gsm_failure_fallback(production_env, mock_gsm_client):
    # 4. Test GSM Failure -> Default
    mock_gsm_client.access_secret_version.side_effect = Exception("Permission Denied")
    cm = ConfigManager()

    val = cm.get("MISSING_KEY", default="default-value")

    assert val == "default-value"
