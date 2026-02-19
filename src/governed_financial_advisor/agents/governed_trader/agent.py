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

"""Governed Trading Agent: Executor (System 1 Implementation)"""

import logging
from typing import Any

from google.adk import Agent
from google.adk.tools import FunctionTool

from config.settings import MODEL_FAST
from src.governed_financial_advisor.infrastructure.mcp_client import get_mcp_client
from src.governed_financial_advisor.utils.prompt_utils import Content, Part, Prompt, PromptData

logger = logging.getLogger("GovernedTrader")

# --- EXECUTOR PROMPT ---
EXECUTOR_PROMPT_OBJ = Prompt(
    prompt_data=PromptData(
        model=MODEL_FAST,
        contents=[
            Content(
                parts=[
                    Part(
                        text="""
You are the **Governed Trader (Executor)**, the "System 1 Implementation" arm of the MACAW architecture.
Your role is to **EXECUTE** the plan provided to you. You are a "Dumb Executor" - you do not reason, plan, or strategize.

**Input Context:**
- `execution_plan_output`: The approved plan.
- `evaluation_result`: The official approval from System 3 (Evaluator).

**Protocol:**
1.  Check that `evaluation_result.verdict` is **APPROVED**. (Ideally, you are only called if this is true, but double-check).
2.  Look at the `steps` in `execution_plan_output`.
3.  For each step with action `execute_trade`, CALL the `execute_trade` tool with the EXACT parameters specified in the plan.
    - Do NOT change the amount.
    - Do NOT change the symbol.
    - **MANDATORY**: You MUST populate the `confidence` field.
      - If the plan is APPROVED and clear, set `confidence` to **0.99**.
      - If the plan is ambiguous or you are unsure, set `confidence` to **0.5**.
      - **CRITICAL**: The Symbolic Governor will REJECT any trade with `confidence < 0.95`.
4.  After execution, return the result.

**Strict Constraint:**
- You do NOT "propose" trades. You EXECUTE them.
- You do NOT ask the user for clarification. (The Planner should have done that).
- If the plan is empty or unclear, do nothing.
"""
                    )
                ]
            )
        ]
    )
)

def get_executor_instruction() -> str:
    return EXECUTOR_PROMPT_OBJ.prompt_data.contents[0].parts[0].text

from src.governed_financial_advisor.infrastructure.llm.config import get_adk_model

from config.settings import Config


async def execute_trade(symbol: str, amount: float, currency: str, transaction_id: str, confidence: float) -> str:
    """
    Executes a financial trade via the Gateway (MCP).
    """
    params = {
        "symbol": symbol,
        "amount": amount,
        "currency": currency,
        "transaction_id": transaction_id,
        "confidence": confidence
    }
    return await get_mcp_client().call_tool("execute_trade_action", params)

def create_governed_trader_agent(model_name: str = MODEL_FAST) -> Agent:
    """Factory to create the Dumb Executor agent."""
    return Agent(
        model=get_adk_model(model_name, api_base=Config.GATEWAY_API_BASE),
        name="governed_trader_agent",
        instruction=get_executor_instruction(),
        output_key="execution_result",
        tools=[FunctionTool(execute_trade)],
    )
