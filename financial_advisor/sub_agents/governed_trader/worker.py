from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from . import prompt
from financial_advisor.tools.trades import execute_trade

MODEL = "gemini-2.5-pro"

worker_agent = LlmAgent(
    model=MODEL,
    name="worker_agent",
    instruction=prompt.TRADING_ANALYST_PROMPT,
    output_key="proposed_trading_strategies_output",
    tools=[FunctionTool(execute_trade)],
)
