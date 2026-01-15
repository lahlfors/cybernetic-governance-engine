from kfp import dsl
from kfp import compiler
from typing import List, Dict

# In a real production setup, we would build a custom container image
# containing the 'src' package and dependencies.
# For this definition, we specify the dependencies and assume the environment matches.
BASE_IMAGE = "python:3.11" # Placeholder for gcr.io/my-project/green-agent:latest

@dsl.component(
    base_image=BASE_IMAGE,
    packages_to_install=["google-adk", "pydantic", "langchain-google-genai"]
)
def risk_discovery_op(
    trading_strategy: str,
    output_gcs_path: str
) -> Dict:
    """
    Component 1: Risk Analysis (A2 Discovery).
    Runs the Risk Analyst agent to identify UCAs.
    """
    import logging
    import asyncio
    # Production Import
    from src.agents.risk_analyst.agent import risk_analyst_agent

    logger = logging.getLogger("RiskDiscovery")
    logger.info(f"Analyzing strategy: {trading_strategy}")

    # Construct Input for the Agent
    # The agent expects specific state keys based on its prompt
    agent_input = {
        "provided_trading_strategy": trading_strategy,
        "execution_plan_output": {
            "plan_id": "pipeline_execution",
            "steps": [], # In a full pipeline, this would come from an upstream Execution Analyst task
            "risk_factors": []
        },
        "user_risk_attitude": "Balanced" # Default or parameterized
    }

    logger.info("🧠 Invoking Risk Agent...")

    # Run the agent (Handling async if needed, ADK invoke is often sync wrapper)
    # If the agent is strictly async, we use asyncio.run
    try:
        # Assuming .invoke() returns the structured output (RiskAssessment)
        # We wrap in asyncio.run just in case the ADK agent is async-native
        async def run_agent():
            return await risk_analyst_agent.invoke(agent_input)

        result = asyncio.run(run_agent())

        # Extract identified UCAs
        # The result should be of type RiskAssessment (Pydantic model)
        ucas = [uca.model_dump() for uca in result.identified_ucas]

        logger.info(f"✅ Identified {len(ucas)} UCAs.")
        return {"ucas": ucas}

    except Exception as e:
        logger.error(f"Risk Discovery Failed: {e}")
        # Fail-safe: Return empty or raise
        raise e

@dsl.component(
    base_image=BASE_IMAGE,
    packages_to_install=["google-adk"]
)
def policy_transpilation_op(
    ucas: Dict,
    generated_rules_path: str
) -> str:
    """
    Component 2: Policy Transpiler.
    Converts UCAs into Python Actions.
    """
    import logging
    # Production Import
    from src.governance.transpiler import transpiler
    from src.agents.risk_analyst.agent import ProposedUCA

    logger = logging.getLogger("PolicyTranspiler")
    logger.info("⚙️ Transpiling Policies...")

    try:
        # Reconstruct Pydantic models from dict input
        raw_ucas = ucas.get("ucas", [])
        proposed_ucas = [ProposedUCA(**u) for u in raw_ucas]

        # Run Transpiler
        code_content = transpiler.transpile_policy(proposed_ucas)

        # In a real component, we might upload this to GCS (output_gcs_path)
        # Here we return it as a string for the deployment step
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
    Updates the runtime environment (NeMo Guardrails).
    """
    import logging
    logger = logging.getLogger("RuleDeployment")

    logger.info(f"🚀 Deploying rules to {target_env}...")

    # In production, this would:
    # 1. Write 'generated_code' to a config repo or bucket.
    # 2. Trigger a rolling restart of the NeMo service.

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
