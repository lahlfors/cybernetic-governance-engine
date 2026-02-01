from enum import Enum

from google.adk.tools import transfer_to_agent
from google.adk.tools.tool_context import ToolContext

from src.governed_financial_advisor.utils.telemetry import get_tracer


class RouterIntent(str, Enum):
    MARKET_ANALYSIS = "MARKET_ANALYSIS"
    TRADING_STRATEGY = "TRADING_STRATEGY"
    EXECUTION_PLAN = "EXECUTION_PLAN"

def route_request(intent: RouterIntent, tool_context: ToolContext) -> str:
    """
    Deterministically routes the request to the appropriate sub-agent based on the intent.
    This enforces the State Graph structure by restricting transitions to valid paths.
    """
    tracer = get_tracer()

    def _do_route():
        if intent == RouterIntent.MARKET_ANALYSIS:
            transfer_to_agent("data_analyst_agent", tool_context)
            return "Routing to Data Analyst.", "data_analyst_agent"

        elif intent == RouterIntent.TRADING_STRATEGY:
            transfer_to_agent("governed_trading_agent", tool_context)
            return "Routing to Governed Trading Agent.", "governed_trading_agent"

        elif intent == RouterIntent.EXECUTION_PLAN:
            transfer_to_agent("execution_analyst_agent", tool_context)
            return "Routing to Execution Analyst.", "execution_analyst_agent"

        return "Error: Invalid Intent.", None

    # Create a trace span for routing
    if tracer:
        with tracer.start_as_current_span("route_request") as span:
            # Handle both string and enum inputs
            intent_str = intent.value if hasattr(intent, 'value') else str(intent)
            span.set_attribute("router.intent", intent_str)
            result, target_agent = _do_route()
            if target_agent:
                span.set_attribute("router.target_agent", target_agent)
            span.set_attribute("router.result", result)
            return result
    else:
        result, _ = _do_route()
        return result

