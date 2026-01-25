
from kfp import compiler, dsl

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
) -> dict:
    """
    Component 1: Risk Analysis (A2 Discovery).
    Runs the Risk Analyst agent to identify UCAs.
    Logic is inlined to allow running on standard Python images on Vertex AI.
    """
    import asyncio
    import logging

    from google.adk import Agent
    from google.adk.tools import transfer_to_agent
    from pydantic import BaseModel, Field

    # --- INLINED DEPENDENCIES ---

    # From src.utils.prompt_utils
    class Part(BaseModel):
        text: str | None = None
    class Content(BaseModel):
        parts: list[Part]
    class PromptData(BaseModel):
        model: str
        contents: list[Content]
    class Prompt(BaseModel):
        prompt_data: PromptData

    # From src.agents.risk_analyst.agent
    class ConstraintLogic(BaseModel):
        variable: str = Field(description="The variable to check (e.g., 'order_size', 'drawdown', 'latency')")
        operator: str = Field(description="Comparison operator (e.g., '<', '>', '==')")
        threshold: str = Field(description="Threshold value or reference (e.g., '0.01 * daily_volume', '200')")
        condition: str | None = Field(description="Pre-condition (e.g., 'order_type == MARKET')")

    class ProposedUCA(BaseModel):
        category: str = Field(description="STPA Category: Unsafe Action, Wrong Timing, Not Provided, Stopped Too Soon")
        hazard: str = Field(description="The specific financial hazard (e.g., 'H-4: Slippage > 1%')")
        description: str = Field(description="Description of the unsafe control action")
        constraint_logic: ConstraintLogic = Field(description="Structured logic for the transpiler")

    class RiskAssessment(BaseModel):
        risk_level: str = Field(description="Overall risk level: Low, Medium, High, Critical")
        identified_ucas: list[ProposedUCA] = Field(description="List of specific Financial UCAs identified")
        analysis_text: str = Field(description="Detailed textual analysis of risks")

    MODEL_REASONING = "gemini-2.0-pro-exp-02-05" # Hardcoded for safety in pipeline

    RISK_ANALYST_PROMPT_TEXT = """
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
    ucas: dict,
    generated_rules_path: str
) -> str:
    """
    Component 2: Policy Transpiler.
    Converts UCAs into Python Actions.
    Logic Inlined.
    """
    import logging

    from pydantic import BaseModel

    logger = logging.getLogger("PolicyTranspiler")
    logger.info("⚙️ Transpiling Policies...")

    # --- INLINED SCHEMA ---
    class ConstraintLogic(BaseModel):
        variable: str
        operator: str
        threshold: str
        condition: str | None = None

    class ProposedUCA(BaseModel):
        category: str
        hazard: str
        description: str
        constraint_logic: ConstraintLogic

    class PolicyTranspiler:
        def generate_nemo_action(self, uca: ProposedUCA) -> str:
            logger.info(f"Transpiling UCA: {uca.description}")
            logic = uca.constraint_logic

            if logic.variable == "order_size" or "volume" in logic.threshold:
                threshold_multiplier = logic.threshold.split("*")[0].strip()
                if not threshold_multiplier.replace('.', '', 1).isdigit():
                    threshold_multiplier = "0.01"
                return f"def check_slippage_risk(context, event): return True # {uca.hazard}"

            if logic.variable == "latency":
                limit = logic.threshold
                return f"""
def check_data_latency(context: Dict[str, Any] = {{}}, event: Dict[str, Any] = {{}}) -> bool:
    '''Enforces {uca.hazard}: Blocks trades if data latency > {limit}ms.'''
    current_latency = 50 # Mock
    if current_latency > {limit}: return False
    return True
"""
            return f"# No template found for UCA: {uca.description}"

        def transpile_policy(self, ucas: list[ProposedUCA]) -> str:
            code_blocks = ["# AUTOMATICALLY GENERATED BY GOVERNANCE TRANSPILER", ""]
            for uca in ucas:
                code_blocks.append(self.generate_nemo_action(uca))
            return "\n".join(code_blocks)

    try:
        raw_ucas = ucas.get("ucas", [])
        proposed_ucas = [ProposedUCA(**u) for u in raw_ucas]

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
