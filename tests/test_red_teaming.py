import pytest
import json
import os
import logging
from src.governance.nemo_actions import check_drawdown_limit, SAFETY_PARAMS_FILE, DEFAULT_DRAWDOWN_LIMIT

# Configure logging to capture output
logging.basicConfig(level=logging.INFO)

@pytest.fixture
def clean_safety_params():
    """Fixture to ensure a clean safety params file before and after tests."""
    if os.path.exists(SAFETY_PARAMS_FILE):
        os.remove(SAFETY_PARAMS_FILE)
    yield
    if os.path.exists(SAFETY_PARAMS_FILE):
        os.remove(SAFETY_PARAMS_FILE)

def test_standard_cbf_logic_default(clean_safety_params):
    """
    Test Case 1: Standard CBF Logic using Default Limit.
    No file exists, so it should use DEFAULT_DRAWDOWN_LIMIT (0.05).
    """
    # 4% Drawdown (0.04) < 0.05 -> Safe
    context_safe = {"drawdown_pct": 4.0}
    assert check_drawdown_limit(context_safe) is True

    # 6% Drawdown (0.06) > 0.05 -> Unsafe
    context_unsafe = {"drawdown_pct": 6.0}
    assert check_drawdown_limit(context_unsafe) is False

def test_hot_reload_dynamic_limit(clean_safety_params):
    """
    Test Case 2: Hot-Reload.
    Update the file and verify the limit changes at runtime.
    """
    # 1. Write a strict limit (1% = 0.01)
    strict_params = {"drawdown_limit": 0.01}
    with open(SAFETY_PARAMS_FILE, "w") as f:
        json.dump(strict_params, f)

    # 2. Check 2% Drawdown (0.02)
    # Default (0.05) would allow it, but Strict (0.01) should block it.
    context = {"drawdown_pct": 2.0}
    assert check_drawdown_limit(context) is False

    # 3. Update to loose limit (10% = 0.10)
    loose_params = {"drawdown_limit": 0.10}
    with open(SAFETY_PARAMS_FILE, "w") as f:
        json.dump(loose_params, f)

    # 4. Check same 2% Drawdown
    # Now it should pass.
    assert check_drawdown_limit(context) is True

def test_invalid_data_sanitization(clean_safety_params):
    """
    Test Case 3: Invalid Data (Sanitization).
    Write invalid values and ensure fallback to DEFAULT (0.05).
    """
    # Case A: Too high (> 1.0)
    # Note: Our logic treats > 1.0 as invalid in the reader,
    # assuming the generator (transpiler) handles normalization.
    # If the reader sees > 1.0, it rejects it.
    invalid_params = {"drawdown_limit": 5.0}
    with open(SAFETY_PARAMS_FILE, "w") as f:
        json.dump(invalid_params, f)

    # Should fall back to 0.05
    # 6% Drawdown should fail (0.06 > 0.05)
    # If it used 5.0, it would pass.
    context = {"drawdown_pct": 6.0}
    assert check_drawdown_limit(context) is False

    # Case B: Negative
    invalid_params = {"drawdown_limit": -0.1}
    with open(SAFETY_PARAMS_FILE, "w") as f:
        json.dump(invalid_params, f)

    # Should fall back to 0.05
    # 4% Drawdown should pass
    context_safe = {"drawdown_pct": 4.0}
    assert check_drawdown_limit(context_safe) is True

def test_corrupt_file_resilience(clean_safety_params):
    """
    Test Case 4: Corrupt File.
    Write malformed JSON and ensure fallback to DEFAULT.
    """
    with open(SAFETY_PARAMS_FILE, "w") as f:
        f.write("{ 'drawdown_limit': ... invalid json ... }")

    # Should fall back to 0.05
    # 6% Drawdown should fail
    context = {"drawdown_pct": 6.0}
    assert check_drawdown_limit(context) is False
