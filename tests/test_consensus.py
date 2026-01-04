import unittest
from unittest.mock import MagicMock, patch
from financial_advisor.consensus import consensus_engine, ConsensusEngine
from financial_advisor.governance import governed_tool, OPAClient
from financial_advisor.tools.trades import execute_trade, TradeOrder

class TestConsensusEngine(unittest.TestCase):
    def test_low_value_trade_skips_consensus(self):
        result = consensus_engine.check_consensus("execute_trade", 5000.0, "AAPL")
        self.assertEqual(result["status"], "SKIPPED")

    def test_high_value_trade_triggers_consensus(self):
        result = consensus_engine.check_consensus("execute_trade", 15000.0, "AAPL")
        # In our mock, it approves by default
        self.assertEqual(result["status"], "APPROVE")
        self.assertTrue("votes" in result)

    @patch("financial_advisor.consensus.ConsensusEngine.check_consensus")
    @patch("financial_advisor.governance.OPAClient.evaluate_policy")
    def test_governed_tool_blocks_consensus_fail(self, mock_policy, mock_consensus):
        # 1. Setup Policy to ALLOW (Pass Layer 2)
        mock_policy.return_value = "ALLOW"

        # 2. Setup Consensus to REJECT (Fail Layer 4)
        mock_consensus.return_value = {"status": "REJECT", "reason": "Simulated Veto"}

        # 3. Create a high value trade
        order = TradeOrder(
            transaction_id="123e4567-e89b-42d3-a456-426614174000",
            trader_id="t1",
            trader_role="senior",
            symbol="AAPL",
            amount=20000.0,
            currency="USD"
        )

        # 4. Call governed tool
        result = execute_trade(order)

        # 5. Assert Blocked
        self.assertIn("BLOCKED: Consensus Engine Rejected", result)
        mock_consensus.assert_called_once()

    @patch("financial_advisor.consensus.ConsensusEngine.check_consensus")
    @patch("financial_advisor.governance.OPAClient.evaluate_policy")
    def test_governed_tool_approves_consensus_pass(self, mock_policy, mock_consensus):
        mock_policy.return_value = "ALLOW"
        mock_consensus.return_value = {"status": "APPROVE"}

        order = TradeOrder(
            transaction_id="123e4567-e89b-42d3-a456-426614174000",
            trader_id="t1",
            trader_role="senior",
            symbol="AAPL",
            amount=20000.0,
            currency="USD"
        )

        result = execute_trade(order)
        self.assertIn("SUCCESS", result)

if __name__ == '__main__':
    unittest.main()
