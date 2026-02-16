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

"""data_analyst_agent for finding information using AlphaVantage MCP"""

import logging
from typing import Optional

from google.adk import Agent
from google.adk.tools import FunctionTool

from config.settings import MODEL_FAST
from src.governed_financial_advisor.utils.prompt_utils import Content, Part, Prompt, PromptData
from src.governed_financial_advisor.tools.market_data_tool import get_market_data

logger = logging.getLogger(__name__)

DATA_ANALYST_PROMPT_OBJ = Prompt(
    prompt_data=PromptData(
        model=MODEL_FAST,
        contents=[
            Content(
                parts=[
                    Part(
                        text="""
Agent Role: data_analyst
Tool Usage: Use the provided `get_market_data` tool.

Overall Goal: To generate a comprehensive and timely market sentiment report for a provided_ticker.

Inputs (from calling agent/environment):
provided_ticker: (string, mandatory) The stock market ticker symbol.

Mandatory Process - Data Collection:
Fetch real-time market data (price and news) using the 'get_market_data' tool.

Expected Final Output (Structured Report):
A comprehensive text report summarizing the sentiment and key news.
The report MUST be formatted in Markdown.
If no data is found, state that clearly.
"""
                    )
                ]
            )
        ]
    )
)

def get_data_analyst_instruction() -> str:
    return DATA_ANALYST_PROMPT_OBJ.prompt_data.contents[0].parts[0].text



from src.governed_financial_advisor.infrastructure.llm.config import get_adk_model

from config.settings import Config

def create_data_analyst_agent(model_name: str = MODEL_FAST) -> Agent:
    """Factory to create data analyst agent."""
    return Agent(
        model=get_adk_model(model_name, api_base=Config.VLLM_FAST_API_BASE),
        name="data_analyst_agent",
        instruction=get_data_analyst_instruction(),
        output_key="market_data_analysis_output",
        tools=[FunctionTool(get_market_data)],
    )
