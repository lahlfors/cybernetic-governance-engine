import asyncio
import logging
import time
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from src.governed_financial_advisor.agents.evaluator.agent import (
    check_market_status,
    create_evaluator_agent,
    verify_policy_opa,
    verify_semantic_nemo,
)
from src.governed_financial_advisor.graph.nodes.adapters import run_adk_agent
from src.governed_financial_advisor.graph.state import AgentState

logger = logging.getLogger("EvaluatorNode")
tracer = trace.get_tracer("src.governed_financial_advisor.graph.nodes.evaluator_node")

async def evaluator_node(state: AgentState) -> dict[str, Any]:
    """
    System 3 Control Node: The "Pessimistic Gatekeeper".
    Runs the Evaluator Agent which orchestrates the simulation.

    Optimization: "Parallel-Internal Evaluator".
    While the Agent itself is sequential, we can perform the tool checks in parallel
    if we implemented custom tool running logic.
    For this implementation, we rely on the Agent's reasoning to call tools.
    However, to strictly enforce the "Optimistic Speed" requirement from the user,
    we can pre-emptively run the checks here in parallel and feed them to the agent context.
    """

    plan = state.get("execution_plan_output")
    if not plan:
        # No plan to evaluate
        return {"next_step": "execution_analyst", "risk_feedback": "No plan provided."}

    # Extract details for checks
    symbol = "UNKNOWN"
    action = "UNKNOWN"
    # Basic parsing if plan is dict
    if isinstance(plan, dict) and "steps" in plan:
        for step in plan["steps"]:
            if "trade" in step.get("action", ""):
                symbol = step.get("parameters", {}).get("symbol", "UNKNOWN")
                action = step.get("action")
                break

    # --- PARALLEL SIMULATION (The Optimization) ---
    # We run the heavy "tools" here in the node wrapper to guarantee parallelism
    # and then pass the results to the Agent to "judge".

    with tracer.start_as_current_span("evaluator.simulation") as span:
        start_time = time.time()

        # 1. Define Tasks (Tools are now Async via Gateway)
        market_task = check_market_status(symbol)
        opa_task = verify_policy_opa(action, str(plan))
        nemo_task = verify_semantic_nemo(str(plan))

        # 2. Run in Parallel
        logger.info(f"⚡ Evaluator: Running Parallel Simulation for {symbol}")
        results = await asyncio.gather(market_task, opa_task, nemo_task, return_exceptions=True)

        market_res, opa_res, nemo_res = results

        latency = (time.time() - start_time) * 1000
        span.set_attribute("simulation.latency_ms", latency)

        # --- SYSTEM 2 INTERCEPTION (Rational Fallback) ---
        if opa_res == "UNCERTAIN":
            logger.warning("🤔 Evaluator: OPA UNCERTAIN -> Redirecting to System 2 Causal Simulation")
            return {
                "evaluation_result": {
                    "verdict": "PENDING_SYSTEM_2",
                    "reasoning": "OPA Policy is Uncertain. Triggering Causal Fallback.",
                    "simulation_logs": [f"OPA Result: {opa_res}"],
                    "policy_check": str(opa_res),
                    "semantic_check": str(nemo_res)
                },
                "next_step": "system_2_simulation",
                "risk_feedback": "Redirecting to Causal Engine for deep verification."
            }
        # --------------------------------------------------

        # 3. Construct Context for the Agent
        simulation_context = (
            f"Pre-Computed Simulation Results:\n"
            f"- Market Status: {market_res}\n"
            f"- Regulatory Policy: {opa_res}\n"
            f"- Semantic Safety: {nemo_res}\n"
        )

    # --- AGENT JUDGMENT ---
    # Now we run the agent, injecting the simulation results as "User" context
    # so it doesn't need to call the tools itself (saving round trips).

    agent = create_evaluator_agent()

    # We inject the context into the message history
    user_msg = f"Please evaluate this plan based on the following simulation results:\n{simulation_context}"

    response = run_adk_agent(agent, user_msg, state["user_id"], "session_evaluator")

    # Parse Result
    # run_adk_agent returns an object with 'answer'. For strict JSON agents,
    # the 'answer' might be the JSON string if configured correctly,
    # or the state update might be handled via tool output key.

    # Since run_adk_agent is a generic adapter, we need to inspect how it updates state.
    # It typically returns a structure. We assume the agent's `output_key` mechanism
    # updates the session state, but here we need to map it to our Graph state.

    # The `run_adk_agent` helper in this repo (implied) likely handles ADK runner execution.
    # We need to extract the `evaluation_result` from the response or the agent's internal logic.
    # For now, we assume the agent's JSON output is in response.answer or structured data.

    # Simplified extraction logic assuming the agent outputs the JSON directly:
    try:
        import json
        eval_result = json.loads(response.answer)
    except:
        # If not strict JSON, we might fallback or check function calls
        # But our agent is configured for JSON.
        # Fallback Mock if parsing fails for this plan step
        eval_result = {
            "verdict": "REJECTED",
            "reasoning": "Failed to parse agent output.",
            "simulation_logs": [str(market_res)],
            "policy_check": str(opa_res),
            "semantic_check": str(nemo_res)
        }

    # Determine Routing
    verdict = eval_result.get("verdict", "REJECTED")
    next_step = "governed_trader" if verdict == "APPROVED" else "execution_analyst"

    return {
        "evaluation_result": eval_result,
        "next_step": next_step,
        "risk_feedback": eval_result.get("reasoning")
    }
