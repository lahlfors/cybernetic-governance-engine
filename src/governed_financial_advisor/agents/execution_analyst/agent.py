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

"""Execution_analyst_agent (Planner) - System 4 Feedforward Engine"""

from typing import Any, Optional

from google.adk import Agent
from pydantic import BaseModel, Field

from config.settings import MODEL_REASONING
from src.governed_financial_advisor.utils.prompt_utils import Content, Part, Prompt, PromptData


# Define the Pydantic schema for the execution plan
class PlanStep(BaseModel):
    id: str = Field(description="Unique identifier for the step")
    action: str = Field(description="Action to perform (e.g., execute_trade, check_price)")
    description: str = Field(description="Description of what this step does")
    parameters: dict[str, Any] = Field(description="Parameters for the action")

class ExecutionPlan(BaseModel):
    plan_id: str = Field(description="Unique identifier for the plan")
    strategy_name: str = Field(description="Name of the strategy (e.g., 'Conservative Dividend Growth')")
    rationale: str = Field(description="Detailed explanation of why this strategy fits the user profile")
    risk_factors: list[str] = Field(description="List of identified risk factors")
    steps: list[PlanStep] = Field(description="Ordered list of execution steps")

    # Context Fields
    user_risk_attitude: Optional[str] = Field(None, description="The user's stated risk attitude")
    user_investment_period: Optional[str] = Field(None, description="The user's investment horizon")

EXECUTION_ANALYST_PROMPT_OBJ = Prompt(
    prompt_data=PromptData(
        model=MODEL_REASONING, # Using reasoning model for planning
        contents=[
            Content(
                parts=[
                    Part(
                        text="""
You are the **Execution Analyst (Planner)**, the "System 4 Feedforward" engine of the MACAW architecture.
Your role is to translate high-level user intent into a concrete, machine-verifiable **Execution Plan**.

**Core Responsibilities:**
1.  **Strategy Formulation:** Analyze the user's risk attitude and investment period. If these are missing, your plan should be to ASK for them.
2.  **Decomposition:** Break down the goal into logical sub-tasks (e.g., "Check Market" -> "Verify Funds" -> "Execute Trade").
3.  **API Grounding:** You do NOT execute actions. You only select tools for the Executor to use later.
    - Available Actions: `execute_trade`, `check_market_status`, `check_balance`.
    - For `execute_trade`, you MUST specify `symbol`, `amount`, and `currency`.

**Input Context:**
- `market_data_analysis_output`: Use this to justify your strategy.
- `user_risk_attitude`: Conservative / Moderate / Aggressive.
- `user_investment_period`: Short / Medium / Long Term.

**Output Requirement:**
You must output a valid JSON object matching the `ExecutionPlan` schema.
- `steps`: A DAG (Directed Acyclic Graph) of actions.
- `rationale`: Explain *why* this plan is safe and suitable.

**Constraint - Missing Info:**
If the user says "buy Apple" but has not specified an amount, your plan should NOT include an `execute_trade` step.
Instead, your plan should be to ask the user for clarification.
HOWEVER, since you output a plan, if you cannot generate a trade plan, generate a "Clarification Plan"
where the action is to ask the user. But ideally, you should transfer back to the supervisor or use a "ask_user" tool if available.
For now, if info is missing, assume a standard default or clearer: The supervisor should handle conversational turns.
You are called when a STRATEGY is needed.

**Handling Rejections:**
If your previous plan was REJECTED by the Evaluator, you will receive `risk_feedback`.
You MUST revise your plan to address the specific feedback (e.g., "Market Closed" -> "Schedule for Open").
"""
                    )
                ]
            )
        ]
    )
)

def get_execution_analyst_instruction() -> str:
    return EXECUTION_ANALYST_PROMPT_OBJ.prompt_data.contents[0].parts[0].text

def create_execution_analyst_agent(model_name: str = MODEL_REASONING) -> Agent:
    """Factory to create execution analyst agent."""
    return Agent(
        model=model_name,
        name="execution_analyst_agent",
        instruction=get_execution_analyst_instruction(),
        output_key="execution_plan_output",
        tools=[],
        # Configure JSON mode for Gemini using ADK's output_schema
        output_schema=ExecutionPlan,
        generate_content_config={
            "response_mime_type": "application/json"
        }
    )
