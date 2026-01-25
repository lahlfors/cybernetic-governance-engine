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

"""Risk Analysis Agent for providing the final risk evaluation and identifying UCAs"""


from google.adk import Agent
from google.adk.tools import transfer_to_agent
from pydantic import BaseModel, Field

from config.settings import MODEL_REASONING
from src.utils.prompt_utils import Content, Part, Prompt, PromptData
from src.governance.policy_loader import PolicyLoader


# Define schema for Constraint Logic (Structured)
class ConstraintLogic(BaseModel):
    variable: str = Field(description="The variable to check (e.g., 'order_size', 'drawdown', 'latency')")
    operator: str = Field(description="Comparison operator (e.g., '<', '>', '==')")
    threshold: str = Field(description="Threshold value or reference (e.g., '0.01 * daily_volume', '200')")
    condition: str | None = Field(description="Pre-condition (e.g., 'order_type == MARKET')")

# Define schema for Financial UCA Identification
class ProposedUCA(BaseModel):
    category: str = Field(description="STPA Category: Unsafe Action, Wrong Timing, Not Provided, Stopped Too Soon")
    hazard: str = Field(description="The specific financial hazard (e.g., 'H-4: Slippage > 1%')")
    description: str = Field(description="Description of the unsafe control action")
    constraint_logic: ConstraintLogic = Field(description="Structured logic for the transpiler")

class RiskAssessment(BaseModel):
    risk_level: str = Field(description="Overall risk level: Low, Medium, High, Critical")
    identified_ucas: list[ProposedUCA] = Field(description="List of specific Financial UCAs identified")
    analysis_text: str = Field(description="Detailed textual analysis of risks")


def get_risk_analyst_instruction() -> str:
    # Use PolicyLoader to fetch dynamic hazard definitions
    loader = PolicyLoader()
    dynamic_hazards = loader.format_as_prompt_context()

    return f"""
Role: You are the 'Risk Discovery Agent' (A2 System).
Your goal is to analyze the proposed trading execution plan and identify specific FINANCIAL UNSAFE CONTROL ACTIONS (UCAs) using STPA methodology.

Input:
- provided_trading_strategy
- execution_plan_output (JSON)
- user_risk_attitude

Task:
Analyze the plan for the following DYNAMICALLY LOADED Hazard Types and define UCAs if risk exists:

{dynamic_hazards}

Output:
Return a structured JSON object (RiskAssessment) containing the list of identified UCAs with their structured `constraint_logic`.

IMMEDIATELY AFTER generating this report, you MUST call `transfer_to_agent("financial_coordinator")` to return control to the main agent.
"""


def create_risk_analyst_agent(model_name: str = MODEL_REASONING) -> Agent:
    """Factory to create risk analyst agent."""
    return Agent(
        model=model_name,
        name="risk_analyst_agent",
        instruction=get_risk_analyst_instruction(),
        output_key="risk_assessment_output",
        tools=[transfer_to_agent],
        output_schema=RiskAssessment,
        generate_content_config={
            "response_mime_type": "application/json"
        }
    )
