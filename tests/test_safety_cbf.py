import unittest
from financial_advisor.safety import safety_filter, ControlBarrierFunction

class TestControlBarrierFunction(unittest.TestCase):
    def setUp(self):
        # Reset state for each test
        safety_filter.current_cash = 100000.0
        safety_filter.min_cash_balance = 1000.0
        safety_filter.gamma = 0.5

    def test_safe_transaction(self):
        """Test a transaction that keeps h(x) well above zero."""
        # Cost 50,000. Next cash 50,000. h(next) = 49,000.
        # h(current) = 99,000. Threshold = 0.5 * 99,000 = 49,500.
        # Wait, if threshold is 49,500 and next h is 49,000, it might fail depending on gamma.

        # Let's calculate exact:
        # h(t) = 99,000
        # Required h(t+1) = 0.5 * 99,000 = 49,500

        # Action: Spend 40,000
        # Next Cash: 60,000 -> h(t+1) = 59,000
        # 59,000 >= 49,500 -> SAFE

        payload = {"amount": 40000.0, "symbol": "AAPL"}
        result = safety_filter.verify_action("execute_trade", payload)
        self.assertEqual(result, "SAFE")

    def test_unsafe_velocity_transaction(self):
        """Test a transaction that is valid by absolute limits but violates velocity (Gamma)."""
        # h(t) = 99,000
        # Required h(t+1) = 49,500

        # Action: Spend 60,000
        # Next Cash: 40,000 -> h(t+1) = 39,000
        # 39,000 < 49,500 -> UNSAFE

        payload = {"amount": 60000.0, "symbol": "AAPL"}
        result = safety_filter.verify_action("execute_trade", payload)
        self.assertIn("UNSAFE", result)
        self.assertIn("Control Barrier Function violation", result)

    def test_absolute_safety_boundary(self):
        """Test a transaction that drops below minimum cash."""
        # Action: Spend 100,000
        # Next Cash: 0 -> h(t+1) = -1000
        # Unsafe because h < 0

        payload = {"amount": 100000.0, "symbol": "AAPL"}
        result = safety_filter.verify_action("execute_trade", payload)
        self.assertIn("UNSAFE", result)

if __name__ == '__main__':
    unittest.main()
