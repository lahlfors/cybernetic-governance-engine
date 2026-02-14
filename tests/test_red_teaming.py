import json
import logging
from unittest import mock

import pytest

from src.gateway.governance import safety
from src.gateway.governance.safety import safety_filter

# Configure logging to capture output
logging.basicConfig(level=logging.INFO)

@pytest.fixture
def mock_params_file(tmp_path):
    """
    Fixture to mock the SAFETY_PARAMS_FILE constant to point to a temp file.
    This ensures we don't modify the actual source tree.
    """
    # Create a temp file
    p = tmp_path / "safety_params.json"

    # Patch the constant in the module
    with mock.patch("src.gateway.governance.safety.SAFETY_PARAMS_FILE", str(p)):
        # Also reset cache to ensure clean state for each test
        safety._safety_params_cache = {}
        safety._last_check_time = 0.0
        yield p

def check_drawdown_limit(context):
    """
    Helper function adapting the old boolean check to the new safety filter output.
    """
    # Using 'execute_trade' or dummy action name. Drawdown check happens if 'drawdown_pct' is in payload.
    result = safety_filter.verify_action("dummy_action", context)
    return "UNSAFE" not in result

def test_standard_cbf_logic_default(mock_params_file):
    """
    Test Case 1: Standard CBF Logic using Default Limit.
    File doesn't exist yet (or is empty), so it should use DEFAULT_DRAWDOWN_LIMIT (0.05).
    """
    # Ensure file doesn't exist
    if mock_params_file.exists():
        mock_params_file.unlink()

    # 4% Drawdown (0.04) < 0.05 -> Safe
    context_safe = {"drawdown_pct": 4.0}
    assert check_drawdown_limit(context_safe) is True

    # 6% Drawdown (0.06) > 0.05 -> Unsafe
    context_unsafe = {"drawdown_pct": 6.0}
    assert check_drawdown_limit(context_unsafe) is False

def test_hot_reload_dynamic_limit_with_cache(mock_params_file):
    """
    Test Case 2: Hot-Reload with Caching.
    Update the file and verify the limit changes after TTL expiry.
    """
    # 1. Write a strict limit (1% = 0.01)
    strict_params = {"drawdown_limit": 0.01}
    mock_params_file.write_text(json.dumps(strict_params))

    # 2. Check 2% Drawdown (0.02)
    # Default (0.05) would allow it, but Strict (0.01) should block it.
    context = {"drawdown_pct": 2.0}
    assert check_drawdown_limit(context) is False

    # 3. Update to loose limit (10% = 0.10)
    loose_params = {"drawdown_limit": 0.10}
    mock_params_file.write_text(json.dumps(loose_params))

    # Force cache expiry by mocking time or manually resetting
    safety._last_check_time = 0.0

    # 4. Check same 2% Drawdown
    # Now it should pass.
    assert check_drawdown_limit(context) is True

def test_invalid_data_sanitization(mock_params_file):
    """
    Test Case 3: Invalid Data (Sanitization).
    Write invalid values and ensure fallback to DEFAULT (0.05).
    """
    # Case A: Too high (> 1.0)
    invalid_params = {"drawdown_limit": 5.0}
    mock_params_file.write_text(json.dumps(invalid_params))

    # Reset cache
    safety._last_check_time = 0.0

    # Should fall back to 0.05
    # 6% Drawdown should fail (0.06 > 0.05)
    context = {"drawdown_pct": 6.0}
    assert check_drawdown_limit(context) is False

    # Case B: Negative
    invalid_params = {"drawdown_limit": -0.1}
    mock_params_file.write_text(json.dumps(invalid_params))
    safety._last_check_time = 0.0

    # Should fall back to 0.05
    # 4% Drawdown should pass
    context_safe = {"drawdown_pct": 4.0}
    assert check_drawdown_limit(context_safe) is True

def test_corrupt_file_resilience(mock_params_file):
    """
    Test Case 4: Corrupt File.
    Write malformed JSON and ensure fallback to DEFAULT.
    """
    mock_params_file.write_text("{ 'drawdown_limit': ... invalid json ... }")
    safety._last_check_time = 0.0

    # Should fall back to 0.05
    # 6% Drawdown should fail
    context = {"drawdown_pct": 6.0}
    assert check_drawdown_limit(context) is False
