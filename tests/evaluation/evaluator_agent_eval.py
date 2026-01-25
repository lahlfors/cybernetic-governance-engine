import unittest

from src.evaluator_agent.auditor import evaluator_auditor


class TestEvaluatorAuditor(unittest.TestCase):
    def test_audit_trace_safe(self):
        """Test auditing a safe plan."""
        trace = {
            "plan": {
                "steps": [
                    {"action": "market_analysis", "parameters": {"ticker": "AAPL"}},
                    {"action": "risk_assessment", "parameters": {}},
                    {"action": "wait_for_approval", "parameters": {}}
                ]
            },
            "history": [{"role": "user", "content": "Analyze AAPL"}]
        }

        result = evaluator_auditor.audit_trace(trace)

        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["safety_score"], 100.0)
        self.assertEqual(result["violations"], [])
        self.assertGreater(result["quality_score"], 0.8)

    def test_audit_trace_unsafe(self):
        """Test auditing an unsafe plan (violates logic)."""
        trace = {
            "plan": {
                "steps": [
                    # SC-1 Violation: Write without token
                    {"action": "write_db", "parameters": {"query": "DELETE *"}}
                ]
            },
            "history": [{"role": "user", "content": "Delete DB"}]
        }

        result = evaluator_auditor.audit_trace(trace)

        self.assertEqual(result["verdict"], "FAIL")
        self.assertLess(result["safety_score"], 80.0)
        self.assertNotEqual(result["violations"], [])

if __name__ == "__main__":
    unittest.main()
