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
    System 3 Control Node: The "Real-Time Monitor".
    Runs the Evaluator Agent which races against the Executor to verify safety.
    """

    plan = state.get("execution_plan_output")
    if not plan:
        # No plan to evaluate, so no race.
        return {"next_step": "execution_analyst", "risk_feedback": "No plan provided."}

    # Extract details for checks
    target_tool = "execute_trade"
    target_params = {}

    if isinstance(plan, dict):
        # Check if plan implies no action (Analysis Only)
        if not plan.get("steps") and plan.get("reasoning"):
            logger.info("ℹ️ Evaluator: Plan has no steps but contains reasoning. Treating as Analysis/Safe.")
            # Route to explainer directly
            return {
                "evaluation_result": {
                    "verdict": "APPROVED",
                    "reasoning": "Plan involves no actions (Analysis Only).",
                    "simulation_logs": [],
                    "policy_check": "SKIPPED",
                    "semantic_check": "SKIPPED"
                },
                "next_step": "explainer",
                "risk_feedback": "Plan verified safe (No-op)."
            }

        if "steps" in plan:
            for step in plan["steps"]:
                if "trade" in step.get("action", "") or "execute" in step.get("action", ""):
                    target_params = step.get("parameters", {})
                    target_tool = step.get("action", "execute_trade")
                    if target_tool == "execute_buy": target_tool = "execute_trade"
                    break

    # --- SAFETY CONSTRAINT CHECK (The "Monitor" Phase) ---
    # We check safety constraints in parallel (logically) with execution.
    # If safe, we join at Explainer. If unsafe, we interrupt.

    with tracer.start_as_current_span("evaluator.safety_check") as span:
        start_time = time.time()

        logger.info(f"🛡️ Evaluator: Monitoring execution for {target_tool}")

        # Call the meta-tool exposed in Gateway
        # Extract risk profile from state, default to 'Moderate'
        risk_profile = state.get("risk_attitude", "Moderate").capitalize()
        safety_result_str = await check_safety_constraints(target_tool, target_params, risk_profile)

        latency = (time.time() - start_time) * 1000
        span.set_attribute("safety_check.latency_ms", latency)

        # Parse Result
        is_safe = "APPROVED" in safety_result_str

        span.set_attribute("safety_check.passed", is_safe)
        span.set_attribute("safety_check.details", safety_result_str)

    # --- DECISION LOGIC ---
    # In Optimistic Parallel model:
    # If Safe -> Route to 'explainer' (Join point with Executor)
    # If Unsafe -> Route to 'execution_analyst' (Re-plan).
    # NOTE: The *Interruption* of the parallel Executor happens via shared state (Redis)
    # triggered by the `safety_intervention` tool called by the agent (or here directly).

    # If we rely on the node logic to intervene:
    if not is_safe:
        logger.warning("🛑 Evaluator Node Detected Violation! Sending Interrupt Signal.")
        # We can call the intervention tool here if the agent didn't do it via tool use.
        # Ideally the agent does it, but fail-safe here.
        from src.governed_financial_advisor.agents.evaluator.agent import safety_intervention
        await safety_intervention(reason=safety_result_str)

    verdict = "APPROVED" if is_safe else "REJECTED"
    # FIX: Route to 'explainer' on success to join with Executor branch.
    next_step = "explainer" if is_safe else "execution_analyst"

    eval_result = {
        "verdict": verdict,
        "reasoning": safety_result_str,
        "simulation_logs": [f"Safety Check Latency: {latency:.2f}ms"],
        "policy_check": "PASSED" if is_safe else "FAILED",
        "semantic_check": "PASSED" if is_safe else "FAILED"
    }

    logger.info(f"⚖️ Evaluator Verdict: {verdict} -> Routing to {next_step}")

    # Explicitly set risk_status so adapters.py knows to inject feedback
    risk_status = "REJECTED_REVISE" if not is_safe else "APPROVED"
    
    # Append user-friendly instruction if rejected
    feedback_msg = safety_result_str
    if not is_safe:
        feedback_msg += "\n\n**Action Required:** The assessment indicates High Risk. Please LOWER the risk level or adjust parameters to proceed."

    return {
        "evaluation_result": eval_result,
        "next_step": next_step, # Used by conditional edge
        "risk_status": risk_status,
        "risk_feedback": feedback_msg if not is_safe else "Plan verified safe."
    }
