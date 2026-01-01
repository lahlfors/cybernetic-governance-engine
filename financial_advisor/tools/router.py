from enum import Enum
from google.adk.tools import transfer_to_agent
from google.adk.tools.tool_context import ToolContext
from pydantic import BaseModel, Field

class RouterIntent(str, Enum):
    MARKET_ANALYSIS = "MARKET_ANALYSIS"
    TRADING_STRATEGY = "TRADING_STRATEGY"
    EXECUTION_PLAN = "EXECUTION_PLAN"
    RISK_ASSESSMENT = "RISK_ASSESSMENT"

def route_request(intent: RouterIntent, context: ToolContext) -> str:
    """
    Deterministically routes the request to the appropriate sub-agent based on the intent.
    This enforces the HD-MDP structure by restricting transitions to valid paths.
    """

    if intent == RouterIntent.MARKET_ANALYSIS:
        transfer_to_agent("data_analyst_agent", context)
        return "Routing to Data Analyst."

    elif intent == RouterIntent.TRADING_STRATEGY:
        transfer_to_agent("governed_trading_agent", context)
        return "Routing to Governed Trading Agent."

    elif intent == RouterIntent.EXECUTION_PLAN:
        transfer_to_agent("execution_analyst_agent", context)
        return "Routing to Execution Analyst."

    elif intent == RouterIntent.RISK_ASSESSMENT:
        transfer_to_agent("risk_analyst_agent", context)
        return "Routing to Risk Analyst."

    return "Error: Invalid Intent."
