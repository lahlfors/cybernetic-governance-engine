import asyncio
import json
import logging
import os

from src.governance.transpiler import transpiler

logger = logging.getLogger("EvaluatorAgent.OfflineUpdater")

async def run_offline_risk_assessment():
    """
    Simulates the 'A2 Discovery' process (Cron Job).
    1. Runs Risk Analyst on current market context.
    2. Transpiles identified UCAs.
    3. Updates 'src/governance/generated_actions.py'.
    """
    logger.info("🕒 Starting Offline Risk Assessment...")

    # Mock Input: In production, this comes from a market scanner or previous plan logs
    mock_input = {
        "provided_trading_strategy": "Momentum Trading on Tech Stocks",
        "execution_plan_output": {
            "plan_id": "test_plan_1",
            "steps": [{"action": "buy", "asset": "NVDA"}],
            "risk_factors": ["High Volatility"]
        },
        "user_risk_attitude": "Balanced"
    }

    # 1. Run Agent
    # We invoke the agent directly.
    # Note: google-adk agents are usually invoked via .invoke() or similar.
    # For this script, we assume the agent exposes a callable interface or we mock the llm call
    # since we don't want to burn tokens in this script constantly.
    # But for the architecture, we show the flow.

    logger.info("🧠 Risk Agent Analyzing...")
    try:
        # result = await risk_analyst_agent.invoke(mock_input)
        # ucas = result.identified_ucas

        # MOCK OUTPUT for reliability in this script
        from src.agents.risk_analyst.agent import ConstraintLogic, ProposedUCA
        ucas = [
            ProposedUCA(
                category="Wrong Order",
                hazard="H-Slippage",
                description="High slippage risk on NVDA.",
                constraint_logic=ConstraintLogic(
                    variable="order_size", operator=">", threshold="0.01 * daily_volume", condition="order_type==MARKET"
                )
            ),
            ProposedUCA(
                category="Unsafe Action",
                hazard="H-Drawdown",
                description="Portfolio drawdown limit risk.",
                constraint_logic=ConstraintLogic(
                    variable="drawdown", operator=">", threshold="4.5", condition="action=='BUY'"
                )
            )
        ]

    except Exception as e:
        logger.error(f"Risk Agent failed: {e}")
        return

    # 2. Transpile
    logger.info("⚙️ Transpiling Rules...")
    py_code, rego_code = transpiler.transpile_policy(ucas)
    safety_params = transpiler.generate_safety_params(ucas)

    # 3. Write to Files
    py_output_path = "src/governance/generated_actions.py"
    with open(py_output_path, "w") as f:
        f.write(py_code)

    rego_output_path = "src/governance/policy/generated_rules.rego"
    with open(rego_output_path, "w") as f:
        f.write(rego_code)

    # Atomic Write for Safety Params
    params_output_path = "src/governance/safety_params.json"
    params_temp_path = params_output_path + ".tmp"
    try:
        with open(params_temp_path, "w") as f:
            json.dump(safety_params, f, indent=2)
        os.replace(params_temp_path, params_output_path)
        logger.info(f"✅ Safety Params Updated: {params_output_path}")
    except Exception as e:
        logger.error(f"Failed to write safety params: {e}")

    logger.info(f"✅ Policy Updated: {py_output_path} and {rego_output_path}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_offline_risk_assessment())
