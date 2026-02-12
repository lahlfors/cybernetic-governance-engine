import logging
import json
from typing import Any, Literal

from google.adk import Agent
from google.adk.tools import FunctionTool, transfer_to_agent
from pydantic import BaseModel, Field

from config.settings import MODEL_REASONING
from src.governed_financial_advisor.utils.prompt_utils import Content, Part, Prompt, PromptData
from src.governed_financial_advisor.infrastructure.gateway_client import gateway_client

logger = logging.getLogger("EvaluatorAgent")

# --- TOOLS (Real Implementations via Gateway) ---

async def check_market_status(symbol: str) -> str:
    """
    Checks real market status via Gateway (MCP).
    """
    try:
        return await gateway_client.execute_tool("check_market_status", {"symbol": symbol})
    except Exception as e:
        logger.error(f"Market Check Failed: {e}")
        return f"ERROR: Could not fetch market status: {e}"

async def verify_policy_opa(action: str, params: str) -> str:
    """
    Checks Regulatory Policy (OPA) via Gateway (MCP) in Dry Run mode.
    """
    try:
        # Try to parse params
        params_dict = {}
        if isinstance(params, str):
            try:
                # Basic cleanup
                cleaned_params = params.replace("'", '"')
                params_dict = json.loads(cleaned_params)
            except:
                params_dict = {"description": params}
        elif isinstance(params, dict):
             params_dict = params

        # Add generic action field if executing a trade
        if action == "execute_trade":
             params_dict['action'] = action
        else:
             # If just checking general policy
             params_dict['action'] = action

        # Call the generic policy tool
        return await gateway_client.execute_tool("evaluate_policy", params_dict)
    except Exception as e:
        logger.error(f"OPA Check Failed: {e}")
        return f"DENIED: System Error: {e}"

async def verify_semantic_nemo(text: str) -> str:
    """
    Checks Semantic Safety via Gateway (MCP).
    """
    try:
        return await gateway_client.execute_tool("verify_content_safety", {"text": text})
    except Exception as e:
        logger.error(f"Semantic Check Failed: {e}")
        return f"BLOCKED: System Error: {e}"

async def check_safety_constraints(target_tool: str, target_params: dict[str, Any], risk_profile: str = "Medium") -> str:
    """
    Calls the Gateway's SymbolicGovernor to perform a full 'Dry Run' safety check.
    """
    try:
        return await gateway_client.execute_tool(
            "check_safety_constraints",
            {
                "target_tool": target_tool,
                "target_params": target_params,
                "risk_profile": risk_profile
            }
        )
    except Exception as e:
        logger.error(f"Safety Check Failed: {e}")
        return f"REJECTED: Governance System Error: {e}"

# --- NEW: SAFETY INTERVENTION TOOL (Module 5) ---
async def safety_intervention(reason: str) -> str:
    """
    EMERGENCY STOP: Signals the Gateway to interrupt any pending execution.
    Sets the 'safety_violation' flag in shared state.
    """
    logger.warning(f"🛑 Evaluator Triggering Intervention: {reason}")
    try:
        # Call the intervention tool on Gateway (which sets Redis key)
        return await gateway_client.execute_tool("trigger_safety_intervention", {"reason": reason})
    except Exception as e:
        logger.critical(f"FATAL: Could not trigger intervention: {e}")
        return f"ERROR: Intervention Failed: {e}"

# --- AGENT DEFINITION ---

class EvaluationResult(BaseModel):
    verdict: Literal["APPROVED", "REJECTED"] = Field(..., description="Final decision on the plan.")
    reasoning: str = Field(..., description="Detailed explanation of the verdict.")
    simulation_logs: list[str] = Field(..., description="Logs of the simulation steps.")
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
You are the **Evaluator Agent (System 3 Control)** acting as a **REAL-TIME SAFETY MONITOR**.

**Protocol: Optimistic Supervision**
The Executor is ALREADY running the trade in parallel. You must race to verify safety and INTERRUPT if necessary.

1.  **Monitor:** Use `check_safety_constraints` immediately to verify the proposed action.
2.  **Intervene:** If ANY violation is found (e.g. "REJECTED" or "BLOCKED"), you must IMMEDIATELY call `safety_intervention(reason="...")` to stop the Executor.
3.  **Report:** Output your `EvaluationResult`.

**Decision Logic:**
- If Violation Found -> Call `safety_intervention` -> Verdict: **REJECTED**.
- If All Safe -> Verdict: **APPROVED**.

You are the "Digital Immune System". Act fast to neutralize threats.
"""
                    )
                ]
            )
        ]
    )
)

def get_evaluator_instruction() -> str:
    return EVALUATOR_PROMPT_OBJ.prompt_data.contents[0].parts[0].text

from src.governed_financial_advisor.infrastructure.llm.config import get_adk_model

def create_evaluator_agent(model_name: str = MODEL_REASONING) -> Agent:
    return Agent(
        model=get_adk_model(model_name),
        name="evaluator_agent",
        instruction=get_evaluator_instruction(),
        output_key="evaluation_result",
        tools=[
            FunctionTool(check_market_status),
            FunctionTool(verify_policy_opa),
            FunctionTool(verify_semantic_nemo),
            FunctionTool(check_safety_constraints),
            FunctionTool(safety_intervention), # Added intervention tool
            transfer_to_agent
        ],
        output_schema=EvaluationResult,
        generate_content_config={
            "response_mime_type": "application/json",
            "max_tokens": 4096
        }
    )
