import unittest
import logging
from financial_advisor.safety import safety_filter
from financial_advisor.infrastructure.redis_client import redis_client

# Configure logging to show up in test output
logging.basicConfig(level=logging.INFO)

class TestControlBarrierFunction(unittest.TestCase):
    def setUp(self):
        # Reset state for each test
        print(f"\n[SetUp] Resetting Redis Key: {safety_filter.redis_key}")
        redis_client.set(safety_filter.redis_key, "100000.0")

        # Verify reset
        val = redis_client.get(safety_filter.redis_key)
        print(f"[SetUp] Value after reset: {val}")

        safety_filter.min_cash_balance = 1000.0
        safety_filter.gamma = 0.5

    def test_safe_transaction(self):
        print("\n--- Test Safe Transaction ---")
        payload = {"amount": 40000.0, "symbol": "AAPL"}
        result = safety_filter.verify_action("execute_trade", payload)
        print(f"[Test] Result: {result}")
        self.assertEqual(result, "SAFE")

    def test_unsafe_velocity_transaction(self):
        print("\n--- Test Unsafe Velocity Transaction ---")
        payload = {"amount": 60000.0, "symbol": "AAPL"}
        result = safety_filter.verify_action("execute_trade", payload)
        print(f"[Test] Result: {result}")

        current_cash = safety_filter._get_current_cash()
        print(f"[Test] Current Cash in Safety Filter: {current_cash}")

        # We expect UNSAFE
        if "UNSAFE" not in result:
            self.fail(f"Expected 'UNSAFE' in result, but got: '{result}'. Current Cash: {current_cash}, Gamma: {safety_filter.gamma}")

        self.assertIn("UNSAFE", result)
        self.assertIn("Control Barrier Function violation", result)

    def test_absolute_safety_boundary(self):
        print("\n--- Test Absolute Boundary ---")
        payload = {"amount": 100000.0, "symbol": "AAPL"}
        result = safety_filter.verify_action("execute_trade", payload)
        self.assertIn("UNSAFE", result)

if __name__ == '__main__':
    unittest.main()
