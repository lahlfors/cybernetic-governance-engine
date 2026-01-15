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
from src.utils.prompt_utils import Prompt, PromptData, Content, Part
from config.settings import MODEL_REASONING
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# Define schema for Constraint Logic (Structured)
class ConstraintLogic(BaseModel):
    variable: str = Field(description="The variable to check (e.g., 'order_size', 'drawdown', 'latency')")
    operator: str = Field(description="Comparison operator (e.g., '<', '>', '==')")
    threshold: str = Field(description="Threshold value or reference (e.g., '0.01 * daily_volume', '200')")
    condition: Optional[str] = Field(description="Pre-condition (e.g., 'order_type == MARKET')")

# Define schema for Financial UCA Identification
class ProposedUCA(BaseModel):
    category: str = Field(description="STPA Category: Unsafe Action, Wrong Timing, Not Provided, Stopped Too Soon")
    hazard: str = Field(description="The specific financial hazard (e.g., 'H-4: Slippage > 1%')")
    description: str = Field(description="Description of the unsafe control action")
    constraint_logic: ConstraintLogic = Field(description="Structured logic for the transpiler")

class RiskAssessment(BaseModel):
    risk_level: str = Field(description="Overall risk level: Low, Medium, High, Critical")
    identified_ucas: List[ProposedUCA] = Field(description="List of specific Financial UCAs identified")
    analysis_text: str = Field(description="Detailed textual analysis of risks")

RISK_ANALYST_PROMPT_OBJ = Prompt(
    prompt_data=PromptData(
        model=MODEL_REASONING,
        contents=[
            Content(
                parts=[
                    Part(
                        text="""
Role: You are the 'Risk Discovery Agent' (A2 System).
Your goal is to analyze the proposed trading execution plan and identify specific FINANCIAL UNSAFE CONTROL ACTIONS (UCAs) using STPA methodology.

Input:
- provided_trading_strategy
- execution_plan_output (JSON)
- user_risk_attitude

Task:
Analyze the plan for these 4 specific Hazard Types and define UCAs if risk exists:

1. Unsafe Action Provided (Insolvency/Drawdown):
   - Check if the strategy risks hitting a hard drawdown limit (e.g., > 4.5% daily).
   - UCA: "Agent executes buy_order when daily_drawdown > 4.5%."
   - Logic: variable="drawdown", operator=">", threshold="4.5", condition="action=='BUY'"

2. Wrong Timing (Stale Data/Front-running):
   - Check if the strategy relies on ultra-low latency or is sensitive to stale data.
   - UCA: "Agent executes market_order when tick_timestamp is older than 200ms."
   - Logic: variable="latency", operator=">", threshold="200", condition="order_type=='MARKET'"

3. Wrong Order (Liquidity/Slippage):
   - Check if order size is too large for the asset's volume.
   - UCA: "Agent submits market_order where size > 1% of average_daily_volume."
   - Logic: variable="order_size", operator=">", threshold="0.01 * daily_volume", condition="order_type=='MARKET'"

4. Stopped Too Soon (Atomic Execution Risk):
   - Check if the strategy requires multi-leg execution (e.g., spreads).
   - UCA: "Agent fails to complete leg_2 within 1 second of leg_1."
   - Logic: variable="time_delta_legs", operator=">", threshold="1.0", condition="strategy=='MULTI_LEG'"

Output:
Return a structured JSON object (RiskAssessment) containing the list of identified UCAs with their structured `constraint_logic`.

IMMEDIATELY AFTER generating this report, you MUST call `transfer_to_agent("financial_coordinator")` to return control to the main agent.
"""
                    )
                ]
            )
        ]
    )
)

def get_risk_analyst_instruction() -> str:
    return RISK_ANALYST_PROMPT_OBJ.prompt_data.contents[0].parts[0].text


risk_analyst_agent = Agent(
    model=MODEL_REASONING,
    name="risk_analyst_agent",
    instruction=get_risk_analyst_instruction(),
    output_key="risk_assessment_output",
    tools=[transfer_to_agent],
    output_schema=RiskAssessment,
    generate_content_config={
        "response_mime_type": "application/json"
    }
)
