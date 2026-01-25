import time
import unittest

from src.governance.nemo_actions import (
    check_approval_token,
    check_atomic_execution,
    check_data_latency,
)


class TestNeMoRefinements(unittest.TestCase):
    def test_approval_token_signature(self):
        """Test AP2 Signature check."""
        self.assertTrue(check_approval_token({"approval_token": "valid_signed_token_123"}))
        self.assertTrue(check_approval_token({"approval_token": "valid_token"})) # Legacy compat
        self.assertFalse(check_approval_token({"approval_token": "bad_sig"}))

    def test_data_latency_fresh(self):
        """Test Latency check with fresh data."""
        now = time.time()
        # 10ms ago
        self.assertTrue(check_data_latency({"tick_timestamp": now - 0.010}))

    def test_data_latency_stale(self):
        """Test Latency check with stale data (>200ms)."""
        now = time.time()
        # 300ms ago
        self.assertFalse(check_data_latency({"tick_timestamp": now - 0.300}))

    def test_atomic_execution_pass(self):
        """Test Atomic check passes when history is present."""
        context = {
            "current_leg_index": 2,
            "audit_trail": [{"leg_index": 1, "status": "filled"}]
        }
        self.assertTrue(check_atomic_execution(context))

    def test_atomic_execution_fail(self):
        """Test Atomic check fails when history is missing."""
        context = {
            "current_leg_index": 2,
            "audit_trail": [] # Leg 1 missing
        }
        self.assertFalse(check_atomic_execution(context))

if __name__ == "__main__":
    unittest.main()
