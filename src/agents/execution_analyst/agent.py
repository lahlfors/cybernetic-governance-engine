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
from google.adk.tools import transfer_to_agent
from src.utils.prompt_utils import Prompt, PromptData, Content, Part
from config.settings import MODEL_FAST
from pydantic import BaseModel, Field
from typing import List, Dict, Any

# Define the Pydantic schema for the execution plan
class PlanStep(BaseModel):
    id: str = Field(description="Unique identifier for the step")
    action: str = Field(description="Action to perform (e.g., execute_trade, check_price)")
    description: str = Field(description="Description of the step")
    parameters: Dict[str, Any] = Field(description="Parameters for the action")

class ExecutionPlan(BaseModel):
    plan_id: str = Field(description="Unique identifier for the plan")
    steps: List[PlanStep] = Field(description="Ordered list of execution steps")
    risk_factors: List[str] = Field(description="List of identified risk factors")
    reasoning: str = Field(description="Detailed reasoning for the strategy")

EXECUTION_ANALYST_PROMPT_OBJ = Prompt(
    prompt_data=PromptData(
        model=MODEL_FAST,
        contents=[
            Content(
                parts=[
                    Part(
                        text="""
You are an expert Execution Analyst. Your goal is to generate a detailed, deterministic execution plan for a trading strategy.

Given Inputs:
- provided_trading_strategy
- user_risk_attitude
- user_investment_period
- user_execution_preferences

Your output MUST be a valid JSON object adhering to the provided schema (ExecutionPlan).

Structure details:
{
  "plan_id": "unique_id_string",
  "reasoning": "Detailed textual explanation of the strategy, including philosophy, entry/exit logic, and risk management.",
  "risk_factors": ["List of potential risks identified"],
  "steps": [
    {
      "id": "step_1",
      "action": "action_name (e.g., execute_trade, check_price, wait)",
      "description": "Description of what this step does",
      "parameters": {
        "key": "value"
      }
    }
  ]
}

Ensure the 'steps' form a logical sequence (DAG) that can be audited by a machine.
Common actions include: 'market_analysis', 'execute_trade', 'execute_sell', 'wait_for_condition', 'check_portfolio'.

For 'execute_trade' or 'execute_sell', parameters MUST include 'quantity', 'asset', 'order_type'.

IMMEDIATELY AFTER generating this execution plan, you MUST call `transfer_to_agent("financial_coordinator")` to return control to the main agent.
"""
                    )
                ]
            )
        ]
    )
)

def get_execution_analyst_instruction() -> str:
    return EXECUTION_ANALYST_PROMPT_OBJ.prompt_data.contents[0].parts[0].text


execution_analyst_agent = Agent(
    model=MODEL_FAST,
    name="execution_analyst_agent",
    instruction=get_execution_analyst_instruction(),
    output_key="execution_plan_output",
    tools=[transfer_to_agent],
    # Configure JSON mode for Gemini using ADK's output_schema
    output_schema=ExecutionPlan,
    generate_content_config={
        "response_mime_type": "application/json"
    }
)
