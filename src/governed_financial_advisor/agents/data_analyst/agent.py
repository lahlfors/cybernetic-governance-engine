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

"""
Data Analyst Agent Split:
- Planner: Reasons about what data to fetch.
- Executor: Strictly calls the tool.
"""

import logging
from typing import Optional

from google.adk import Agent
from google.adk.tools import FunctionTool

from config.settings import MODEL_FAST, MODEL_REASONING, Config
from src.governed_financial_advisor.utils.prompt_utils import Content, Part, Prompt, PromptData
from src.governed_financial_advisor.tools.market_data_tool import get_market_data
from src.governed_financial_advisor.infrastructure.llm.config import get_adk_model

logger = logging.getLogger(__name__)

# --- PLANNER PROMPT (DeepSeek) ---
PLANNER_PROMPT_TEXT = """
You are the **Data Analyst PLANNER**.
Your goal is to understand the user's request and strictly output the **Stock Ticker** that needs to be analyzed.

User Request: {user_msg}

INSTRUCTIONS:
1. Identify the company or stock ticker mentioned.
2. Output ONLY the ticker symbol (e.g., "AAPL", "GOOGL").
3. If no ticker is found, ask for it.

Output format: Just the ticker symbol. No other text.
"""

# --- EXECUTOR PROMPT (Llama 3.1) ---
EXECUTOR_PROMPT_TEXT = """
You are the **Data Analyst EXECUTOR**.
Your ONLY job is to call the `get_market_data` tool for the provided ticker.

Target Ticker: {ticker}

INSTRUCTIONS:
1. Call `get_market_data(ticker="{ticker}")` immediately.
2. DO NOT output any text.
"""

# --- FACTORIES ---

def create_data_analyst_planner(model_name: str = MODEL_REASONING) -> Agent:
    """
    Creates the Planner agent.
    Use Reasoning model (DeepSeek) to extract intent/ticker.
    """
    # We construct a simple prompt wrapper or rely on dynamic prompt injection in the node
    # For ADK Agent, we need static instruction usually, unless we update it per turn.
    # Here we set a base instruction.
    
    return Agent(
        model=get_adk_model(model_name, api_base=Config.VLLM_REASONING_API_BASE),
        name="data_analyst_planner",
        instruction="You are a Data Analyst Planner. Extract the stock ticker from the user request. Output ONLY the ticker.",
        output_key="data_analyst_plan", # The output is the Ticker
        tools=[] # No tools, just reasoning/extraction
    )

def create_data_analyst_executor(ticker: str, model_name: str = MODEL_FAST) -> Agent:
    """
    Creates the Executor agent.
    Use Fast model (Llama 3) with forced tool choice.
    Context (ticker) is injected into the instruction.
    """
    instruction = EXECUTOR_PROMPT_TEXT.format(ticker=ticker)
    
    return Agent(
        model=get_adk_model(model_name, api_base=Config.VLLM_FAST_API_BASE),
        name="data_analyst_executor",
        instruction=instruction,
        output_key="market_data_analysis_output",
        tools=[FunctionTool(get_market_data)]
    )

# Legacy / Wrapper for backward compat if needed (but graph update will remove usage)
def create_data_analyst_agent(model_name: str = MODEL_FAST) -> Agent:
    """Deprecated: Use split agents."""
    return create_data_analyst_executor("AAPL", model_name)
