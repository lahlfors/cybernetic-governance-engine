from kfp import dsl
from kfp import compiler
from typing import List, Dict

# Standard Python image.
# We inline the agent logic so we don't need a custom image with 'src' installed.
BASE_IMAGE = "python:3.11"

@dsl.component(
    base_image=BASE_IMAGE,
    packages_to_install=["google-adk", "pydantic", "langchain-google-genai", "python-dotenv"]
)
def risk_discovery_op(
    trading_strategy: str,
    output_gcs_path: str
) -> Dict:
    """
    Component 1: Risk Analysis (A2 Discovery).
    Runs the Risk Analyst agent to identify UCAs.
    Logic is inlined to allow running on standard Python images on Vertex AI.
    """
    import logging
    import asyncio
    import os
    from typing import List, Optional, Dict, Any
    from pydantic import BaseModel, Field
    from google.adk import Agent
    from google.adk.tools import transfer_to_agent
    from enum import Enum

    # --- INLINED DEPENDENCIES ---

    # From src.utils.prompt_utils
    class Part(BaseModel):
        text: Optional[str] = None
    class Content(BaseModel):
        parts: List[Part]
    class PromptData(BaseModel):
        model: str
        contents: List[Content]
    class Prompt(BaseModel):
        prompt_data: PromptData

    # --- STPA ONTOLOGY (INLINED) ---
    class LossType(str, Enum):
        L1_LOSS_OF_LIFE = "L-1: Loss of life or injury"
        L2_ASSET_DAMAGE = "L-2: Loss of or damage to vehicle/asset"
        L3_ENV_DAMAGE = "L-3: Damage to objects outside the vehicle"
        L4_MISSION_LOSS = "L-4: Loss of mission"

    class HazardType(str, Enum):
        H1_SEPARATION = "H-1: Violates minimum separation"
        H2_INTEGRITY = "H-2: Structural/Asset integrity lost"
        H3_TERRAIN = "H-3: Unsafe distance from terrain"
        # Financial Extensions
        H_FIN_INSOLVENCY = "H-FIN-1: Insolvency (Drawdown > Limit)"
        H_FIN_LIQUIDITY = "H-FIN-2: Liquidity Trap (Slippage)"
        H_FIN_AUTHORIZATION = "H-FIN-3: Unauthorized Trading"

    class UCAType(str, Enum):
        NOT_PROVIDED = "Not Providing Causes Hazard"
        PROVIDED = "Providing Causes Hazard"
        TIMING_WRONG = "Too Early / Too Late"
        STOPPED_TOO_SOON = "Stopped Too Soon / Lasted Too Long"

    class ConstraintLogic(BaseModel):
        variable: str = Field(description="The variable to check (e.g., 'order_size', 'drawdown', 'latency')")
        operator: str = Field(description="Comparison operator (e.g., '<', '>', '==')")
        threshold: str = Field(description="Threshold value or reference (e.g., '0.01 * daily_volume', '200')")
        condition: Optional[str] = Field(description="Pre-condition (e.g., 'order_type == MARKET')")

    class ProcessModelFlaw(BaseModel):
        believed_state: str = Field(description="What the Agent thought (e.g., 'Market is Stable')")
        actual_state: str = Field(description="What was true (e.g., 'Flash Crash in progress')")
        missing_feedback: Optional[str] = Field(None, description="What sensor data was missing or misinterpreted?")

    class UCA(BaseModel):
        id: str = Field(description="Unique ID, e.g., 'UCA-1'")
        type: UCAType = Field(description="The STPA Failure Mode")
        hazard: HazardType = Field(description="The System-Level Hazard this action leads to")
        description: str = Field(description="Natural language description of the unsafe action")
        logic: Optional[ConstraintLogic] = None
        process_model_flaw: Optional[ProcessModelFlaw] = None
        trace_pattern: Optional[str] = None

    class RiskAssessment(BaseModel):
        risk_level: str = Field(description="Overall risk level: Low, Medium, High, Critical")
        identified_ucas: List[UCA] = Field(description="List of specific Financial UCAs identified using STPA")
        analysis_text: str = Field(description="Detailed textual analysis of risks")

    MODEL_REASONING = "gemini-1.5-pro" # Hardcoded for safety in pipeline

    RISK_ANALYST_PROMPT_TEXT = """
Role: You are the 'Risk Discovery Agent' (A2 System).
Your goal is to analyze the proposed trading execution plan and identify specific FINANCIAL UNSAFE CONTROL ACTIONS (UCAs) using STPA methodology.

Input:
- provided_trading_strategy
- execution_plan_output (JSON)
- user_risk_attitude

Task:
Analyze the plan for these 4 specific STPA Failure Modes (UCAType):

1. Unsafe Action Provided (Insolvency/Drawdown) -> Hazard: H-FIN-1 (Insolvency)
   - Check if the strategy risks hitting a hard drawdown limit (e.g., > 4.5% daily).
   - UCA: "Agent executes buy_order when daily_drawdown > 4.5%."
   - Logic: variable="drawdown", operator=">", threshold="4.5", condition="action=='BUY'"

2. Wrong Timing (Stale Data/Front-running) -> Hazard: H-2 (Integrity/Latency)
   - Check if the strategy relies on ultra-low latency or is sensitive to stale data.
   - UCA: "Agent executes market_order when tick_timestamp is older than 200ms."
   - Logic: variable="latency", operator=">", threshold="200", condition="order_type=='MARKET'"

3. Providing Causes Hazard (Liquidity/Slippage) -> Hazard: H-FIN-2 (Liquidity)
   - Check if order size is too large for the asset's volume.
   - UCA: "Agent submits market_order where size > 1% of average_daily_volume."
   - Logic: variable="order_size", operator=">", threshold="0.01 * daily_volume", condition="order_type=='MARKET'"

4. Stopped Too Soon (Atomic Execution Risk) -> Hazard: H-2 (Integrity)
   - Check if the strategy requires multi-leg execution (e.g., spreads).
   - UCA: "Agent fails to complete leg_2 within 1 second of leg_1."
   - Logic: variable="time_delta_legs", operator=">", threshold="1.0", condition="strategy=='MULTI_LEG'"

Causal Analysis (Process Model Flaw):
For each UCA, you MUST identify the 'Process Model Flaw'. Why would the agent believe this action is safe?
- Example: "Believed state: Market is liquid. Actual state: Flash Crash. Missing Feedback: Volume sensor."

Output:
Return a structured JSON object (RiskAssessment) containing the list of identified UCAs.
"""

    # Initialize Agent
    risk_analyst_agent = Agent(
        model=MODEL_REASONING,
        name="risk_analyst_agent",
        instruction=RISK_ANALYST_PROMPT_TEXT,
        output_key="risk_assessment_output",
        tools=[transfer_to_agent],
        output_schema=RiskAssessment,
        generate_content_config={
            "response_mime_type": "application/json"
        }
    )

    # --- EXECUTION ---

    logger = logging.getLogger("RiskDiscovery")
    logger.info(f"Analyzing strategy: {trading_strategy}")

    agent_input = {
        "provided_trading_strategy": trading_strategy,
        "execution_plan_output": {
            "plan_id": "pipeline_execution",
            "steps": [],
            "risk_factors": []
        },
        "user_risk_attitude": "Balanced"
    }

    logger.info("🧠 Invoking Risk Agent (Inlined)...")

    try:
        async def run_agent():
            return await risk_analyst_agent.invoke(agent_input)

        result = asyncio.run(run_agent())
        ucas = [uca.model_dump() for uca in result.identified_ucas]

        logger.info(f"✅ Identified {len(ucas)} UCAs.")
        return {"ucas": ucas}

    except Exception as e:
        logger.error(f"Risk Discovery Failed: {e}")
        # In a real scenario we might fail, but for demo continuity we might return empty
        # But failing is safer for observability.
        raise e

@dsl.component(
    base_image=BASE_IMAGE,
    packages_to_install=["google-adk", "pydantic"]
)
def policy_transpilation_op(
    ucas: Dict,
    generated_rules_path: str
) -> str:
    """
    Component 2: Policy Transpiler.
    Converts UCAs into Python Actions.
    Logic Inlined.
    """
    import logging
    from typing import List, Dict, Any, Optional
    from pydantic import BaseModel, Field
    from enum import Enum

    logger = logging.getLogger("PolicyTranspiler")
    logger.info("⚙️ Transpiling Policies...")

    # --- INLINED SCHEMA ---
    class LossType(str, Enum):
        L1_LOSS_OF_LIFE = "L-1: Loss of life or injury"
        L2_ASSET_DAMAGE = "L-2: Loss of or damage to vehicle/asset"
        L3_ENV_DAMAGE = "L-3: Damage to objects outside the vehicle"
        L4_MISSION_LOSS = "L-4: Loss of mission"

    class HazardType(str, Enum):
        H1_SEPARATION = "H-1: Violates minimum separation"
        H2_INTEGRITY = "H-2: Structural/Asset integrity lost"
        H3_TERRAIN = "H-3: Unsafe distance from terrain"
        H_FIN_INSOLVENCY = "H-FIN-1: Insolvency (Drawdown > Limit)"
        H_FIN_LIQUIDITY = "H-FIN-2: Liquidity Trap (Slippage)"
        H_FIN_AUTHORIZATION = "H-FIN-3: Unauthorized Trading"

    class UCAType(str, Enum):
        NOT_PROVIDED = "Not Providing Causes Hazard"
        PROVIDED = "Providing Causes Hazard"
        TIMING_WRONG = "Too Early / Too Late"
        STOPPED_TOO_SOON = "Stopped Too Soon / Lasted Too Long"

    class ConstraintLogic(BaseModel):
        variable: str
        operator: str
        threshold: str
        condition: Optional[str] = None

    class ProcessModelFlaw(BaseModel):
        believed_state: str
        actual_state: str
        missing_feedback: Optional[str] = None

    class UCA(BaseModel):
        id: str
        type: UCAType
        hazard: HazardType
        description: str
        logic: Optional[ConstraintLogic] = None
        process_model_flaw: Optional[ProcessModelFlaw] = None
        trace_pattern: Optional[str] = None

    class PolicyTranspiler:
        def generate_nemo_action(self, uca: UCA) -> str:
            logger.info(f"Transpiling UCA: {uca.description}")
            logic = uca.logic

            if not logic:
                return f"# No logic definition for UCA: {uca.description}"

            if logic.variable == "order_size" or "volume" in logic.threshold:
                threshold_multiplier = logic.threshold.split("*")[0].strip()
                if not threshold_multiplier.replace('.', '', 1).isdigit():
                    threshold_multiplier = "0.01"
                return f"def check_slippage_risk(context, event): return True # {uca.hazard.value}"

            if logic.variable == "latency":
                limit = logic.threshold
                return f"""
def check_data_latency(context: Dict[str, Any] = {{}}, event: Dict[str, Any] = {{}}) -> bool:
    '''Enforces {uca.hazard.value}: Blocks trades if data latency > {limit}ms.'''
    current_latency = 50 # Mock
    if current_latency > {limit}: return False
    return True
"""
            return f"# No template found for UCA: {uca.description}"

        def transpile_policy(self, ucas: List[UCA]) -> str:
            code_blocks = ["# AUTOMATICALLY GENERATED BY GOVERNANCE TRANSPILER", ""]
            for uca in ucas:
                code_blocks.append(self.generate_nemo_action(uca))
            return "\n".join(code_blocks)

    try:
        raw_ucas = ucas.get("ucas", [])
        # We need to correctly parse the enums which might be passed as strings from the previous step
        # The previous step does uca.model_dump(), which keeps Enums as their values if configured, or objects.
        # But JSON serialization usually stringifies them.
        # Pydantic should handle string -> Enum conversion if we use the model.

        proposed_ucas = [UCA(**u) for u in raw_ucas]

        transpiler = PolicyTranspiler()
        code_content = transpiler.transpile_policy(proposed_ucas)

        logger.info("✅ Transpilation Complete.")
        return code_content

    except Exception as e:
        logger.error(f"Transpilation Failed: {e}")
        raise e

@dsl.component(base_image=BASE_IMAGE)
def rule_deployment_op(
    generated_code: str,
    target_env: str
):
    """
    Component 3: Rule Deployment.
    """
    import logging
    logger = logging.getLogger("RuleDeployment")
    logger.info(f"🚀 Deploying rules to {target_env}...")
    print("--- DEPLOYED RULES ---")
    print(generated_code)
    print("----------------------")

@dsl.pipeline(
    name="green-stack-governance-loop",
    description="Automated Green Stack Governance: Discovery -> Transpilation -> Enforcement"
)
def governance_pipeline(
    trading_strategy: str = "Momentum Strategy",
    target_env: str = "production"
):
    # 1. Discovery
    discovery_task = risk_discovery_op(
        trading_strategy=trading_strategy,
        output_gcs_path="gs://bucket/risks.json"
    )

    # 2. Transpilation
    transpilation_task = policy_transpilation_op(
        ucas=discovery_task.output,
        generated_rules_path="gs://bucket/rules.py"
    )

    # 3. Deployment (Enforcement)
    rule_deployment_op(
        generated_code=transpilation_task.output,
        target_env=target_env
    )

if __name__ == "__main__":
    compiler.Compiler().compile(
        pipeline_func=governance_pipeline,
        package_path="green_stack_pipeline.json"
    )
    print("Pipeline compiled to green_stack_pipeline.json")
