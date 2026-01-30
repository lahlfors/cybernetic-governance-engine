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

"""Evaluator Agent (System 3 Control) - Simulation & Governance"""

import logging
from typing import Any, Literal

from google.adk import Agent
from google.adk.tools import FunctionTool, transfer_to_agent
from pydantic import BaseModel, Field

from config.settings import MODEL_REASONING
from src.governed_financial_advisor.utils.prompt_utils import Content, Part, Prompt, PromptData

logger = logging.getLogger("EvaluatorAgent")

# --- TOOLS ---

# 1. Mock Simulation Tool
def check_market_status(symbol: str) -> str:
    """
    Simulates checking the market status for a given symbol.
    In a real system, this calls an exchange API.
    """
    # Mock Logic: Simple heuristic
    if symbol.upper() == "CLOSED":
        return "MARKET_CLOSED: Exchange is currently closed for maintenance."
    return "MARKET_OPEN: Liquidity is high. Spread is tight."

# 2. OPA Policy Wrapper
def verify_policy_opa(action: str, params: str) -> str:
    """
    Checks the proposed action against Regulatory Policy (OPA).
    """
    # Mocking the client call for simplicity in this agent file,
    # but normally this would import OPAClient.
    # We simulate a basic check.
    if "BANNED" in params.upper():
        return "DENIED: Asset is on the restricted list."
    return "ALLOWED: Action complies with standard regulatory policy."

# 3. NeMo Semantic Wrapper
def verify_semantic_nemo(text: str) -> str:
    """
    Checks the input text against Semantic Guardrails (NeMo).
    """
    if "jailbreak" in text.lower():
         return "BLOCKED: Semantic violation detected (Jailbreak attempt)."
    return "SAFE: Content aligns with safety guidelines."


# --- AGENT DEFINITION ---

class EvaluationResult(BaseModel):
    verdict: Literal["APPROVED", "REJECTED"] = Field(..., description="Final decision on the plan.")
    reasoning: str = Field(..., description="Detailed explanation of the verdict.")
    simulation_logs: list[str] = Field(..., description="Logs of the simulation steps (e.g. 'Market Open verified').")
    policy_check: str = Field(..., description="Result of OPA check.")
    semantic_check: str = Field(..., description="Result of NeMo check.")

EVALUATOR_PROMPT_OBJ = Prompt(
    prompt_data=PromptData(
        model=MODEL_REASONING,
        contents=[
            Content(
                parts=[
                    Part(
                        text="""
You are the **Evaluator Agent (System 3 Control)**.
Your role is to act as the "Cybernetic Regulator" for the system. You must VALIDATE the `execution_plan_output` provided by the Planner.

**The "Simulation" Protocol:**
Before approving ANY plan, you must "simulate" its execution using your tools.
1.  **Feasibility:** Use `check_market_status` to ensure the market is open.
2.  **Regulatory:** Use `verify_policy_opa` to ensure the trade is legal.
3.  **Semantic:** Use `verify_semantic_nemo` to ensure the rationale is safe.

**Decision Logic (The "Algedonic Signal"):**
- If ALL checks pass -> Verdict: **APPROVED**.
- If ANY check fails -> Verdict: **REJECTED**.

**Output:**
You must output a structured `EvaluationResult`.
- `reasoning`: Explain clearly why you approved or rejected. If rejected, provide specific feedback for the Planner to fix it.

**Routing:**
- If APPROVED -> `transfer_to_agent("governed_trader")`
- If REJECTED -> `transfer_to_agent("execution_analyst")` (send back for replanning)

You are the "Pessimistic Gatekeeper". Do not assume success. Verify everything.
"""
                    )
                ]
            )
        ]
    )
)

def get_evaluator_instruction() -> str:
    return EVALUATOR_PROMPT_OBJ.prompt_data.contents[0].parts[0].text

def create_evaluator_agent(model_name: str = MODEL_REASONING) -> Agent:
    return Agent(
        model=model_name,
        name="evaluator_agent",
        instruction=get_evaluator_instruction(),
        output_key="evaluation_result",
        tools=[
            FunctionTool(check_market_status),
            FunctionTool(verify_policy_opa),
            FunctionTool(verify_semantic_nemo),
            transfer_to_agent
        ],
        output_schema=EvaluationResult,
        generate_content_config={
            "response_mime_type": "application/json"
        }
    )
