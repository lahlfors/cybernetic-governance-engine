import unittest
import sys
import asyncio
from unittest.mock import MagicMock, patch

# Ensure src is in path
sys.path.append(".")

# Mock the singletons module before importing actions
# This prevents real singletons from initializing (connecting to OPA, etc.)
mock_symbolic_governor = MagicMock()
mock_stpa_validator = MagicMock()
mock_safety_filter = MagicMock()

# Setup hierarchy
mock_symbolic_governor.stpa_validator = mock_stpa_validator
mock_symbolic_governor.safety_filter = mock_safety_filter

# Apply patch
modules_to_patch = {
    "src.gateway.governance.singletons": MagicMock(symbolic_governor=mock_symbolic_governor)
}
patcher = patch.dict("sys.modules", modules_to_patch)
patcher.start()

from src.gateway.governance.nemo.actions import (
    check_approval_token,
    check_data_latency,
    check_drawdown_limit,
    check_slippage_risk,
    check_atomic_execution
)

class TestNeMoActions(unittest.IsolatedAsyncioTestCase):
    async def test_check_approval_token_valid(self):
        # Setup mock to return no violations
        mock_stpa_validator.validate.return_value = []
        context = {"approval_token": "valid_token"}

        result = await check_approval_token(context)
        self.assertTrue(result)
        mock_stpa_validator.validate.assert_called_with("execute_trade", {"approval_token": "valid_token"})

    async def test_check_approval_token_invalid(self):
        # Setup mock to return violations
        mock_stpa_validator.validate.return_value = ["Missing Token"]
        context = {} # Missing token

        result = await check_approval_token(context)
        self.assertFalse(result)

    async def test_check_data_latency_valid(self):
        mock_stpa_validator.validate.return_value = []
        context = {"latency_ms": 50}

        result = await check_data_latency(context)
        self.assertTrue(result)

    async def test_check_data_latency_missing(self):
        # Fail closed on missing latency
        context = {}
        result = await check_data_latency(context)
        self.assertFalse(result)

    async def test_check_drawdown_limit_safe(self):
        mock_safety_filter.verify_action.return_value = "SAFE"
        context = {"amount": 100}

        result = await check_drawdown_limit(context)
        self.assertTrue(result)

    async def test_check_drawdown_limit_unsafe(self):
        mock_safety_filter.verify_action.return_value = "UNSAFE: Drawdown Limit Exceeded"
        context = {"amount": 10000}

        result = await check_drawdown_limit(context)
        self.assertFalse(result)

    async def test_check_atomic_execution(self):
        # Currently fail closed
        result = await check_atomic_execution({})
        self.assertFalse(result)

if __name__ == "__main__":
    unittest.main()
