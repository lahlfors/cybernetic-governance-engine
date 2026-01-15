import unittest
from src.governance.nemo_actions import check_approval_token, check_latency

class TestNeMoActions(unittest.TestCase):
    def test_check_approval_token_valid(self):
        context = {"approval_token": "valid_token"}
        self.assertTrue(check_approval_token(context))

    def test_check_approval_token_invalid(self):
        context = {"approval_token": "invalid"}
        self.assertFalse(check_approval_token(context))

    def test_check_approval_token_missing(self):
        context = {}
        self.assertFalse(check_approval_token(context))

    def test_check_latency(self):
        # Default mock is 100ms, so it should pass
        self.assertTrue(check_latency({}))

if __name__ == "__main__":
    unittest.main()
