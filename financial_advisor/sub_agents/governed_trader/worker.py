from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from google.adk.tools import transfer_to_agent

from .prompt import get_trading_analyst_instruction
from financial_advisor.tools.trades import propose_trade

MODEL = "gemini-2.5-pro"

worker_agent = LlmAgent(
    model=MODEL,
    name="worker_agent",
    instruction=get_trading_analyst_instruction(),
    output_key="proposed_trading_strategies_output",
    tools=[FunctionTool(propose_trade), transfer_to_agent],
)
