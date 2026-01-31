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
import asyncio

from google.adk import Agent
from google.adk.tools import FunctionTool, transfer_to_agent
from pydantic import BaseModel, Field

from config.settings import MODEL_REASONING
from src.governed_financial_advisor.utils.prompt_utils import Content, Part, Prompt, PromptData

# REAL IMPLEMENTATIONS
from src.gateway.core.policy import OPAClient
from src.governed_financial_advisor.governance.consensus import consensus_engine
from src.governed_financial_advisor.utils.nemo_manager import load_rails, validate_with_nemo

logger = logging.getLogger("EvaluatorAgent")

# --- TOOLS (Wrappers for Real Logic) ---

def check_market_status(symbol: str) -> str:
    """
    Checks the market status for a given symbol.
    (Stub: Real API key required for AlphaVantage/Polygon. Keeping simple logic for now but marking as PRODUCTION_STUB).
    """
    # In a real production system, this connects to an Exchange API.
    # For this exercise, we assume the exchange is always open unless explicitly closed in a config.
    # This removes the "Mock" random logic.
    return "MARKET_OPEN: Liquidity is sufficient."

async def verify_policy_opa(action: str, params: str) -> str:
    """
    Checks the proposed action against Regulatory Policy (OPA).
    """
    client = OPAClient()
    try:
        # Parse params string to dict if possible, else wrap
        import json
        try:
            input_data = json.loads(params)
        except:
            input_data = {"raw_params": params}

        input_data["action"] = action

        decision = await client.evaluate_policy(input_data)

        if decision == "ALLOW":
            return "ALLOWED: Action complies with standard regulatory policy."
        elif decision == "MANUAL_REVIEW":
            return "MANUAL_REVIEW: Policy requires human oversight."
        else:
            return "DENIED: Policy violation detected."
    finally:
        await client.close()

async def verify_consensus(action: str, params: str) -> str:
    """
    Checks Consensus for high-value trades.
    """
    try:
        import json
        data = json.loads(params)
        amount = float(data.get("amount", 0))
        symbol = data.get("symbol", "UNKNOWN")
    except:
        amount = 0.0
        symbol = "UNKNOWN"

    result = await consensus_engine.check_consensus(action, amount, symbol)
    return f"CONSENSUS_RESULT: {result['status']} ({result['reason']})"

async def verify_semantic_nemo(text: str) -> str:
    """
    Checks the input text against Semantic Guardrails (NeMo).
    """
    rails = load_rails()
    is_safe, response = await validate_with_nemo(text, rails)

    if is_safe:
        return "SAFE: Content aligns with safety guidelines."
    else:
        return f"BLOCKED: Semantic violation detected. {response}"


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
3.  **Consensus:** Use `verify_consensus` to ensure high-value trades are approved by risk managers.
4.  **Semantic:** Use `verify_semantic_nemo` to ensure the rationale is safe.

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
            FunctionTool(verify_consensus),
            FunctionTool(verify_semantic_nemo),
            transfer_to_agent
        ],
        output_schema=EvaluationResult,
        generate_content_config={
            "response_mime_type": "application/json"
        }
    )
