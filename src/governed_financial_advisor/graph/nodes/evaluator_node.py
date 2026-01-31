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
    verify_consensus
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
    We pre-emptively run the checks here in parallel (real async) and feed them to the agent context.
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

    # If action is empty, default to "plan_review"
    if action == "UNKNOWN":
        action = "plan_review"

    # --- PARALLEL SIMULATION (The Optimization) ---
    # We run the heavy "tools" here in the node wrapper to guarantee parallelism
    # and then pass the results to the Agent to "judge".

    with tracer.start_as_current_span("evaluator.simulation") as span:
        start_time = time.time()

        # 1. Define Tasks
        # check_market_status is Sync (Thread)
        market_task = asyncio.to_thread(check_market_status, symbol)

        # verify_policy_opa is Async (Task)
        opa_task = verify_policy_opa(action, str(plan))

        # verify_semantic_nemo is Async (Task)
        nemo_task = verify_semantic_nemo(str(plan))

        # verify_consensus is Async (Task)
        consensus_task = verify_consensus(action, str(plan))

        # 2. Run in Parallel
        logger.info(f"⚡ Evaluator: Running Parallel Simulation for {symbol}")
        # Use return_exceptions=True to prevent one failure from crashing the whole node
        results = await asyncio.gather(market_task, opa_task, nemo_task, consensus_task, return_exceptions=True)

        market_res, opa_res, nemo_res, consensus_res = results

        # Log errors if any task failed
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                logger.error(f"Simulation Task {i} failed: {res}")

        latency = (time.time() - start_time) * 1000
        span.set_attribute("simulation.latency_ms", latency)

        # 3. Construct Context for the Agent
        simulation_context = (
            f"Pre-Computed Simulation Results:\n"
            f"- Market Status: {market_res}\n"
            f"- Regulatory Policy: {opa_res}\n"
            f"- Consensus Check: {consensus_res}\n"
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
