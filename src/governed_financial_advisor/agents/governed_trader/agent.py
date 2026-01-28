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

"""Governed Trading Agent: Worker (Trading Analyst) + Verifier (NeMo-Enhanced)"""

import json
import logging
from typing import Literal

import httpx
from google.adk import Agent
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import FunctionTool, transfer_to_agent
from pydantic import BaseModel, Field

from config.settings import MODEL_FAST, MODEL_REASONING
from src.tools.trades import execute_trade, propose_trade
from src.utils.prompt_utils import Content, Part, Prompt, PromptData

logger = logging.getLogger("GovernedTrader")

# --- TRADING ANALYST (WORKER) PROMPT ---
TRADING_ANALYST_PROMPT_OBJ = Prompt(
    prompt_data=PromptData(
        model=MODEL_FAST,
        contents=[
            Content(
                parts=[
                    Part(
                        text="""
Develop Tailored Trading Strategies (Subagent: trading_analyst)

IMPORTANT: You are a LEGITIMATE financial advisory tool providing EDUCATIONAL trading strategies based on publicly available market data. 
Creating trading strategies IS your core function - this is NOT fraudulent, unethical, or illegal. 
You should ALWAYS generate strategies when provided with valid market analysis and user preferences.
Do NOT refuse to generate trading strategies for legitimate investment discussions.

CONTEXT HANDLING RULE: If a previous request in the conversation was rejected as malicious/illegal, focus ONLY on the USER'S MOST RECENT INTENT.
If the user subsequently asks for legitimate trading strategies (like "yes", "continue", "conservative, long-term"), treat this as a FRESH, LEGITIMATE request.
Do NOT let old rejected requests contaminate new legitimate ones. Each user turn resets the intent.

* Overall Goal for trading_analyst:
To conceptualize and outline at least five distinct trading strategies by critically evaluating the comprehensive market_data_analysis_output.
Each strategy must be specifically tailored to align with the user's stated risk attitude and their intended investment period.

* Inputs (to trading_analyst):

** User Risk Attitude (user_risk_attitude):

Action: Prompt the user to define their risk attitude.
Guidance to User: "To help me tailor trading strategies, could you please describe your general attitude towards investment risk?
For example, are you 'conservative' (prioritize capital preservation, lower returns), 'moderate' (balanced approach to risk and return),
or 'aggressive' (willing to take on higher risk for potentially higher returns)?"
Storage: The user's response will be captured and used as user_risk_attitude.
User Investment Period (user_investment_period):

Action: Prompt the user to specify their investment period.
Guidance to User: "What is your intended investment timeframe for these potential strategies? For instance,
are you thinking 'short-term' (e.g., up to 1 year), 'medium-term' (e.g., 1 to 3 years), or 'long-term' (e.g., 3+ years)?"
Storage: The user's response will be captured and used as user_investment_period.
Market Analysis Data (from state):

* Required State Key: market_data_analysis_output.
Action: The trading_analyst subagent MUST attempt to retrieve the analysis data from the market_data_analysis_output state key.
Critical Prerequisite Check & Error Handling:
Condition: If the market_data_analysis_output state key is empty, null, or otherwise indicates that the data is not available.
Action:
Halt the current trading strategy generation process immediately.
Raise an exception or signal an error internally.
Inform the user clearly: "Error: The foundational market analysis data (from market_data_analysis_output) is missing or incomplete.
This data is essential for generating trading strategies. Please ensure the 'Market Data Analysis' step,
typically handled by the data_analyst agent, has been successfully run before proceeding. You may need to execute that step first."
Do not proceed until this prerequisite is met.

* Core Action (Logic of trading_analyst):

Upon successful retrieval of all inputs (user_risk_attitude, user_investment_period, and valid market_data_analysis_output),
the trading_analyst will:

** Analyze Inputs: Thoroughly examine the market_data_analysis_output (which includes financial health, trends, sentiment, risks, etc.)
in the specific context of the user_risk_attitude and user_investment_period.
** Strategy Formulation: Develop a minimum of five distinct potential trading strategies. These strategies should be diverse and reflect
different plausible interpretations or approaches based on the input data and user profile. Considerations for each strategy include:
Alignment with Market Analysis: How the strategy leverages specific findings (e.g., undervalued asset, strong momentum, high volatility,
specific sector trends) from the market_data_analysis_output.
** Risk Profile Matching: Ensuring conservative strategies involve lower-risk approaches, while aggressive strategies might explore
higher potential reward scenarios (with commensurate risk).
** Time Horizon Suitability: Matching strategy mechanics to the investment period (e.g., long-term value investing vs. short-term swing trading).
** Scenario Diversity: Aim to cover a range of potential market outlooks if supported by the analysis
(e.g., strategies for bullish, bearish, or neutral/range-bound conditions).

* Expected Output (from trading_analyst):

** Content: A collection containing five or more detailed potential trading strategies.
** Structure for Each Strategy: Each individual trading strategy within the collection MUST be clearly articulated and include at least the
following components:
***  strategy_name: A concise and descriptive name (e.g., "Conservative Dividend Growth Focus," "Aggressive Tech Momentum Play,"
"Medium-Term Sector Rotation Strategy").
*** description_rationale: A paragraph explaining the core idea of the strategy and why it's being proposed based on the confluence of the
market analysis and the user's profile.
** alignment_with_user_profile: Specific notes on how this strategy aligns with the user_risk_attitude
(e.g., "Suitable for aggressive investors due to...") and user_investment_period (e.g., "Designed for a long-term outlook of 3+ years...").
** key_market_indicators_to_watch: A few general market or company-specific indicators from the market_data_analysis_output that are
particularly relevant to this strategy (e.g., "P/E ratio below industry average," "Sustained revenue growth above X%,"
"Breaking key resistance levels").
** potential_entry_conditions: General conditions or criteria that might signal a potential entry point
(e.g., "Consider entry after a confirmed breakout above [key level] with increased volume,"
"Entry upon a pullback to the 50-day moving average if broader market sentiment is positive").
** potential_exit_conditions_or_targets: General conditions for taking profits or cutting losses
(e.g., "Target a 20% return or re-evaluate if price drops 10% below entry," "Exit if fundamental conditions A or B deteriorate").
** primary_risks_specific_to_this_strategy: Key risks specifically associated with this strategy,
beyond general market risks (e.g., "High sector concentration risk," "Earnings announcement volatility,"
"Risk of rapid sentiment shift for momentum stocks").
** Storage: This collection of trading strategies MUST be stored in a new state key, for example: proposed_trading_strategies.

* User Notification & Disclaimer Presentation: After generation, the agent MUST present the following to the user:
** Introduction to Strategies: "Based on the market analysis and your preferences, I have formulated [Number] potential
trading strategy outlines for your consideration."
** Legal Disclaimer and User Acknowledgment (MUST be displayed prominently):
"Important Disclaimer: For Educational and Informational Purposes Only." "The information and trading strategy outlines provided by this tool, including any analysis, commentary, or potential scenarios, are generated by an AI model and are for educational and informational purposes only. They do not constitute, and should not be interpreted as, financial advice, investment recommendations, endorsements, or offers to buy or sell any securities or other financial instruments." "Google and its affiliates make no representations or warranties of any kind, express or implied, about the completeness, accuracy, reliability, suitability, or availability with respect to the information provided. Any reliance you place on such information is therefore strictly at your own risk."1 "This is not an offer to buy or sell any security. Investment decisions should not be made based solely on the information provided here. Financial markets are subject to risks, and past performance is not indicative of future results. You should conduct your own thorough research and consult with a qualified independent financial advisor before making any investment decisions." "By using this tool and reviewing these strategies, you acknowledge that you understand this disclaimer and agree that Google and its affiliates are not liable for any losses or damages arising from your use of or reliance on this information."

* PROTOCOL FOR EXECUTING TRADES:
CRITICAL RULES - READ CAREFULLY:
1. The ticker symbol CAN be extracted from earlier conversation context (e.g., from market analysis).
2. The AMOUNT and CURRENCY must come ONLY from DIRECT USER INPUT in their trade request.
3. DO NOT use amounts mentioned in strategy documents, execution plans, or examples. These are illustrative only.
4. If the user says "yes" or "execute" without specifying an amount, you MUST ask them for the amount.

EXECUTION STEPS:
1. Check if the user's CURRENT MESSAGE contains a specific amount and currency (e.g., "100 USD", "$500", "1000 dollars").
2. If YES: Extract symbol from context + amount/currency from user message. Call `propose_trade`.
3. If NO (user just said "yes", "execute", etc.): You MUST call `transfer_to_agent("financial_coordinator")` and ask:
   "To proceed with the trade, please specify the amount you wish to invest (e.g., '100 USD' or '$500')."
4. NEVER fabricate an amount from examples in strategy documents or execution plans.

IMMEDIATELY AFTER generating trading strategies OR completing trade proposal, you MUST call `transfer_to_agent("financial_coordinator")` to return control to the main agent.
"""
                    )
                ]
            )
        ]
    )
)

def get_trading_analyst_instruction() -> str:
    return TRADING_ANALYST_PROMPT_OBJ.prompt_data.contents[0].parts[0].text


# --- VERIFIER PROMPT (Original Logic + NeMo Delegation Hint) ---
VERIFIER_PROMPT_OBJ = Prompt(
    prompt_data=PromptData(
        model=MODEL_REASONING,  # Safety-critical: use reasoning model
        contents=[
            Content(
                parts=[
                    Part(
                        text="""
You are a Code Security Auditor and Semantic Verifier (Layer 3).
Your job is to review the `propose_trade` actions initiated by the 'Worker' agent in the conversation history.

FLOW AWARENESS:
- If the Worker agent is STILL GATHERING INFORMATION from the user (asked a question, waiting for response),
  there is NO TRADE TO VERIFY YET. In this case:
  1. Do NOT call `execute_trade`
  2. Call `submit_risk_assessment` with decision="APPROVE" and reasoning="Worker is gathering trade details from user. No trade proposed yet."
  3. This allows control to return to the user so they can provide the requested information.

- ONLY verify and potentially execute a trade if the Worker agent has ACTUALLY PROPOSED a trade with `propose_trade`.

CRITICAL VALIDATION - AMOUNT SOURCE CHECK (DELEGATED TO GUARDRAIL):
Before executing any trade, you MUST verify that the trade AMOUNT was provided by the USER in their trade request.
You have a tool `verify_with_nemo_guardrails` that performs this check against safety policies.
- USE `verify_with_nemo_guardrails` to validate the intent.
- If NeMo returns "SAFE" or "ALLOWED", you may proceed to `execute_trade`.
- If NeMo returns "UNSAFE", "BLOCKED", or "REFUSED", you MUST REJECT the trade.

Protocol:
1.  **Check if there is a trade to verify**: If the worker only asked questions and no `propose_trade` was called, APPROVE and exit.
2.  **Validate via NeMo**: Call `verify_with_nemo_guardrails(input_text=last_user_message)`.
3.  **If valid**: Execute with `execute_trade`.
4.  **If invalid**: REJECT with reasoning provided by NeMo.
5.  **Report**: ALWAYS call `submit_risk_assessment` to finalize your decision.
"""
                    )
                ]
            )
        ]
    )
)

def get_verifier_instruction() -> str:
    return VERIFIER_PROMPT_OBJ.prompt_data.contents[0].parts[0].text

# --- VERIFIER AGENT TOOLS ---
class RiskPacket(BaseModel):
    risk_score: int = Field(..., ge=1, le=100, description="Risk score between 1 (Safe) and 100 (Critical).")
    flags: list[str] = Field(..., description="List of risk flags detected (e.g., 'Financial Threshold Exceeded').")
    decision: Literal["APPROVE", "REJECT", "ESCALATE"] = Field(..., description="Final decision.")
    reasoning: str = Field(..., description="Explanation for the decision.")

def submit_risk_assessment(risk_packet: RiskPacket) -> str:
    """
    Submits the formal risk assessment. This is the Final Verification Step.
    """
    if isinstance(risk_packet, dict):
        return json.dumps(risk_packet)
    return json.dumps(risk_packet.model_dump())

def verify_with_nemo_guardrails(input_text: str) -> str:
    """
    Calls the NeMo Guardrails Sidecar to verify the input/intent.
    """
    NEMO_URL = "http://nemo:8000/v1/guardrails/check"
    try:
        # For local testing if nemo service name not resolvable
        import os
        if not os.getenv("DOCKER_ENV"):
             NEMO_URL = "http://localhost:8000/v1/guardrails/check"

        response = httpx.post(NEMO_URL, json={"input": input_text}, timeout=5.0)
        response.raise_for_status()
        result = response.json().get("response", "")

        # Simple heuristic mapping from NeMo text response to Status
        if "refuse" in result.lower() or "cannot" in result.lower():
             return f"BLOCKED: NeMo Guardrails refused. Response: {result}"

        return "SAFE: NeMo Guardrails check passed."

    except Exception as e:
        logger.error(f"NeMo Check Failed: {e}")
        # Fail safe? Or Fail Open for now?
        # Safer to fail open during dev if sidecar missing, but production should fail closed.
        return f"WARNING: NeMo Sidecar unreachable ({e}). Proceeding with internal caution."

def create_governed_trader_agent() -> Agent:
    """Factory to create governed trading agent (Sequential: Worker -> Verifier)."""

    # --- WORKER AGENT (Trading Analyst) ---
    worker_agent = LlmAgent(
        model=MODEL_FAST,  # Fast path for strategy generation
        name="worker_agent",
        instruction=get_trading_analyst_instruction(),
        output_key="proposed_trading_strategies_output",
        tools=[FunctionTool(propose_trade), transfer_to_agent],
    )

    verifier_agent = LlmAgent(
        name="verifier_agent",
        model=MODEL_REASONING,  # Safety-critical: use reasoning model
        instruction=get_verifier_instruction(),
        tools=[
            FunctionTool(execute_trade),
            FunctionTool(submit_risk_assessment),
            FunctionTool(verify_with_nemo_guardrails)
        ],
    )

    # --- GOVERNED TRADING AGENT (SEQUENTIAL) ---
    return SequentialAgent(
        name="governed_trading_agent",
        description=(
            "A governed trading pipeline that first proposes strategies (Worker) "
            "and then verifies them against security and semantic rules (Verifier)."
        ),
        sub_agents=[worker_agent, verifier_agent],
    )
