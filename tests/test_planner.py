import unittest
from financial_advisor.planning.hierarchical import ExplicitStatePlanner, MacroState

class TestHierarchicalPlanner(unittest.TestCase):
    def setUp(self):
        self.planner = ExplicitStatePlanner()

    def test_plan_analysis(self):
        state = self.planner.plan_macro_action("Analyze AAPL price", {})
        self.assertEqual(state, MacroState.ANALYSIS)

        actions = self.planner.expand_primitive_actions(state, {"symbol": "AAPL"})
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].tool_name, "get_market_data")
        self.assertEqual(actions[0].tool_args["symbol"], "AAPL")

    def test_plan_strategy_from_buy_intent(self):
        # Initial buy request should go to Strategy (Propose), not Execute
        state = self.planner.plan_macro_action("Buy 100 shares", {})
        self.assertEqual(state, MacroState.STRATEGY)

        actions = self.planner.expand_primitive_actions(state, {})
        self.assertEqual(actions[0].tool_name, "propose_trade")

    def test_plan_execution_sequence(self):
        # If we just finished Risk Assessment, we can Execute
        context = {"last_state": MacroState.RISK_ASSESSMENT, "trade_details": {"amount": 100}}
        state = self.planner.plan_macro_action("Buy 100 shares", context)
        self.assertEqual(state, MacroState.EXECUTION)

        actions = self.planner.expand_primitive_actions(state, context)
        self.assertEqual(actions[0].tool_name, "execute_trade")
        self.assertEqual(actions[0].tool_args["amount"], 100)

if __name__ == '__main__':
    unittest.main()
