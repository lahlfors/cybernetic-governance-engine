# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Execution_analyst_agent for finding the ideal execution strategy"""

from google.adk import Agent
from google.adk.tools import FunctionTool

from .prompt import get_trading_analyst_instruction
from financial_advisor.tools.trades import execute_trade

MODEL = "gemini-2.5-pro"

trading_analyst_agent = Agent(
    model=MODEL,
    name="trading_analyst_agent",
    instruction=get_trading_analyst_instruction(),
    output_key="proposed_trading_strategies_output",
    tools=[FunctionTool(execute_trade)],
)
