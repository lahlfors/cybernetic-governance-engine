import asyncio
import logging
import json
import time
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from src.governed_financial_advisor.agents.evaluator.agent import (
    create_evaluator_agent,
    check_safety_constraints
)
from src.governed_financial_advisor.graph.nodes.adapters import run_adk_agent
from src.governed_financial_advisor.graph.state import AgentState

logger = logging.getLogger("EvaluatorNode")
tracer = trace.get_tracer("src.governed_financial_advisor.graph.nodes.evaluator_node")

async def evaluator_node(state: AgentState) -> dict[str, Any]:
    """
    System 3 Control Node: The "Pessimistic Gatekeeper".
    Runs the Evaluator Agent which orchestrates the simulation.

    Refactored to enforce safety via `check_safety_constraints` tool.
    """

    plan = state.get("execution_plan_output")
    if not plan:
        # No plan to evaluate
        return {"next_step": "execution_analyst", "risk_feedback": "No plan provided."}

    # Extract details for checks
    # Basic parsing if plan is dict (from Planner)
    target_tool = "execute_trade" # Default assumption for high risk
    target_params = {}

    if isinstance(plan, dict) and "steps" in plan:
        for step in plan["steps"]:
            if "trade" in step.get("action", "") or "execute" in step.get("action", ""):
                target_params = step.get("parameters", {})
                target_tool = step.get("action", "execute_trade")
                # Fix naming mismatch if needed
                if target_tool == "execute_buy": target_tool = "execute_trade"
                break

    # --- SAFETY CONSTRAINT CHECK (The "Check" Phase) ---
    # We run the comprehensive safety check (System 3) via the Gateway.
    # This replaces the previous ad-hoc parallel checks.

    with tracer.start_as_current_span("evaluator.safety_check") as span:
        start_time = time.time()

        logger.info(f"🛡️ Evaluator: Running Safety Constraints Check for {target_tool}")

        # Call the new meta-tool
        safety_result_str = await check_safety_constraints(target_tool, target_params)

        latency = (time.time() - start_time) * 1000
        span.set_attribute("safety_check.latency_ms", latency)

        # Parse the result string from the tool
        # Expected: "APPROVED: ..." or "REJECTED: ..."
        is_safe = "APPROVED" in safety_result_str

        span.set_attribute("safety_check.passed", is_safe)
        span.set_attribute("safety_check.details", safety_result_str)

    # --- DECISION LOGIC ---
    # We update the state based on the safety check.
    # We can still run the agent if we want a conversational explanation,
    # but the HARD gating logic is here in the node code (Graph Control).

    verdict = "APPROVED" if is_safe else "REJECTED"
    next_step = "governed_trader" if is_safe else "execution_analyst"

    eval_result = {
        "verdict": verdict,
        "reasoning": safety_result_str,
        "simulation_logs": [f"Safety Check Latency: {latency:.2f}ms"],
        "policy_check": "PASSED" if is_safe else "FAILED",
        "semantic_check": "PASSED" if is_safe else "FAILED" # Covered by safety check now
    }

    logger.info(f"⚖️ Evaluator Verdict: {verdict} -> Routing to {next_step}")

    return {
        "evaluation_result": eval_result,
        "next_step": next_step,
        "risk_feedback": safety_result_str if not is_safe else "Plan verified safe."
    }
