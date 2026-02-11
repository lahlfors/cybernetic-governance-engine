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

"""data_analyst_agent for finding information using Computer Use (Python Sandbox)"""

import logging

import requests
from google.adk import Agent
from google.adk.tools import FunctionTool

from config.settings import MODEL_FAST, Config
from src.governed_financial_advisor.utils.prompt_utils import (
    Content,
    Part,
    Prompt,
    PromptData,
)

logger = logging.getLogger(__name__)

DATA_ANALYST_PROMPT_OBJ = Prompt(
    prompt_data=PromptData(
        model=MODEL_FAST,
        contents=[
            Content(
                parts=[
                    Part(
                        text="""
Agent Role: data_analyst (Computer Use)
Tool Usage: Use the provided `execute_python_analysis` tool.

Overall Goal: To generate a comprehensive and timely market sentiment report for a provided_ticker.

Inputs (from calling agent/environment):
provided_ticker: (string, mandatory) The stock market ticker symbol.

Mandatory Process - Data Collection & Analysis:
You have access to a Python environment with `pandas` (pd) and `yfinance` (yf) pre-installed.
Write Python code to fetch data (e.g., `df = yf.download(ticker)`) and perform analysis (e.g., calculating RSI, Moving Averages, volatility).
Execute the code using the `execute_python_analysis` tool.
Use the output of the code execution to form your final report.

Expected Final Output (Structured Report):
A comprehensive text report summarizing the analysis performed and the results.
"""
                    )
                ]
            )
        ]
    )
)

def get_data_analyst_instruction() -> str:
    return DATA_ANALYST_PROMPT_OBJ.prompt_data.contents[0].parts[0].text

def execute_python_analysis(code: str) -> str:
    """
    Executes Python code to analyze market data.
    PRE-INSTALLED LIBRARIES: pandas (as pd), yfinance (as yf).

    Example:
    df = yf.download("AAPL")
    print(df['Close'].mean())
    """
    try:
        # Call the local sidecar (running src/sandbox/main.py)
        response = requests.post(
            Config.SANDBOX_URL,
            json={"code": code},
            timeout=10 # Fail fast if infinite loop
        )
        result = response.json()

        if result["status"] == "error":
            return f"Runtime Error: {result.get('error')}\nStdout: {result.get('stdout')}\nStderr: {result.get('stderr')}"
        return f"Output:\n{result.get('stdout')}"

    except Exception as e:
        logger.error(f"Sandbox Call Failed: {e}")
        return f"Sandbox Connection Failed: {e!s}"

from src.governed_financial_advisor.infrastructure.llm.config import get_adk_model


def create_data_analyst_agent(model_name: str = MODEL_FAST) -> Agent:
    """Factory to create data analyst agent."""
    return Agent(
        model=get_adk_model(model_name),
        name="data_analyst_agent",
        instruction=get_data_analyst_instruction(),
        output_key="market_data_analysis_output",
        tools=[FunctionTool(execute_python_analysis)],
    )
