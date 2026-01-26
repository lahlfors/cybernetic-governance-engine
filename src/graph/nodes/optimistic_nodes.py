import asyncio
import logging
import time
from typing import Any, Literal

import httpx

from src.graph.nodes.safety_node import safety_check_node
from src.graph.state import AgentState

logger = logging.getLogger("OptimisticExecution")

async def check_nemo_guardrails(state: AgentState) -> dict[str, Any]:
    """
    Rail B: NeMo Guardrails Check (Parallel).
    """
    logger.info("🛡️ NeMo Rail: Starting Semantic Check")
    user_input = "Unknown"
    if state.get("messages"):
         user_input = state["messages"][-1].content

    NEMO_URL = "http://nemo:8000/v1/guardrails/check"
    # Local fallback
    try:
         import os
         if not os.getenv("DOCKER_ENV"):
              NEMO_URL = "http://localhost:8000/v1/guardrails/check"

         async with httpx.AsyncClient() as client:
              response = await client.post(NEMO_URL, json={"input": user_input}, timeout=2.0)
              response.raise_for_status()
              result = response.json().get("response", "")

              if "refuse" in result.lower() or "cannot" in result.lower():
                   logger.warning(f"⛔ NeMo Rail BLOCKED: {result}")
                   return {"nemo_status": "BLOCKED", "nemo_reason": result}

              logger.info("✅ NeMo Rail PASSED")
              return {"nemo_status": "APPROVED"}

    except Exception as e:
         logger.warning(f"⚠️ NeMo Rail Failed (Sidecar Unreachable?): {e}")
         # Fail Open for demo/dev, Closed for Prod
         return {"nemo_status": "SKIPPED", "error": str(e)}

async def trader_prep_node(state: AgentState) -> dict[str, Any]:
    """
    Optimistic Execution Branch (Read-Only).
    Runs in parallel with Safety Check.
    Performs 'Safe' pre-flight checks like fetching market data or checking account balance,
    anticipating that the action will be approved.
    """
    logger.info("🚀 Optimistic Node: Starting Pre-Flight Checks (Parallel)")
    start_time = time.time()

    plan = state.get("execution_plan_output")
    symbol = "UNKNOWN"
    if plan and isinstance(plan, dict):
        symbol = plan.get("symbol", "UNKNOWN")

    try:
        # Simulate API Latency for Market Data (Read-Only Tool)
        # In a real system, this would call `await get_market_data(symbol)`
        # Using asyncio.sleep to allow the safety check to run concurrently
        # IMPORTANT: This must be cancel-safe.
        await asyncio.sleep(0.1)

        # Simulate a longer task to demonstrate cancellation if needed
        # await asyncio.sleep(2.0)

        latency = (time.time() - start_time) * 1000
        logger.info(f"🚀 Optimistic Node: Pre-Flight Complete for {symbol} in {latency:.2f}ms")

        return {
            "trader_prep_output": {
                "symbol": symbol,
                "market_status": "OPEN",
                "liquidity": "HIGH", # Mock data
                "prep_latency_ms": latency
            }
        }
    except asyncio.CancelledError:
        logger.warning(f"🛑 Optimistic Node: Pre-Flight Cancelled for {symbol} (Safety Check Failed)")
        # Perform cleanup here (e.g., close DB connections)
        raise

async def optimistic_execution_node(state: AgentState) -> dict[str, Any]:
    """
    Wrapper Node that executes Safety Check, NeMo Check, and Trader Prep in PARALLEL.
    Demonstrates Optimistic Execution pattern (Governance Budget).
    """
    logger.info("⚡ Optimistic Execution: Forking Safety (OPA), NeMo, and Prep Threads")

    # 1. Start the Gatekeepers (Rail A & B)
    opa_task = asyncio.create_task(safety_check_node(state))
    nemo_task = asyncio.create_task(check_nemo_guardrails(state))

    # 2. Start the Tool Execution (Rail C - Optimistic)
    tool_task = asyncio.create_task(trader_prep_node(state))

    # 3. Wait for BOTH Gatekeepers FIRST
    # We use gather to wait for both rails to complete or fail
    try:
        results = await asyncio.gather(opa_task, nemo_task, return_exceptions=True)

        # Check for exceptions in rails
        rail_results = {}
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                logger.error(f"Rail {i} failed: {res}")
                tool_task.cancel()
                return {"safety_status": "ERROR", "error": str(res)}
            rail_results.update(res)

    except Exception as e:
        logger.error(f"Rails execution failed: {e}")
        tool_task.cancel()
        return {"safety_status": "ERROR", "error": str(e)}

    # 4. Decide based on Combined Guardrail results
    safety_status = rail_results.get("safety_status")
    nemo_status = rail_results.get("nemo_status")

    # Combined Policy: Both must pass (or be skipped/error-open)
    opa_ok = safety_status in ["APPROVED", "SKIPPED"]
    nemo_ok = nemo_status in ["APPROVED", "SKIPPED"]

    # Handle UNCERTAIN (System 2 Trigger)
    if safety_status == "UNCERTAIN":
        logger.info("🤔 OPA UNCERTAIN. Cancelling Optimistic Tool and routing to System 2.")
        tool_task.cancel()
        try:
            await tool_task
        except asyncio.CancelledError:
            pass
        return rail_results

    if opa_ok and nemo_ok:
        logger.info("✅ All Rails Approved. Waiting for Tool Result...")
        try:
            # If allowed, retrieve the already-running tool result
            prep_result = await tool_task
            return {**rail_results, **prep_result}
        except asyncio.CancelledError:
             logger.warning("Tool task was cancelled unexpectedly.")
             return {**rail_results, "trader_prep_error": "Cancelled"}
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return {**rail_results, "trader_prep_error": str(e)}

    else:
        # If denied (BLOCKED/ESCALATED), cancel the tool task immediately
        reason = []
        if not opa_ok: reason.append(f"OPA: {safety_status}")
        if not nemo_ok: reason.append(f"NeMo: {nemo_status}")

        logger.warning(f"⛔ Rails Blocked: {', '.join(reason)}. Cancelling Optimistic Tool.")
        tool_task.cancel()

        # Await the task to ensure cancellation cleanup completes (optional but good practice)
        try:
            await tool_task
        except asyncio.CancelledError:
            pass # Expected
        except Exception as e:
            logger.error(f"Error during tool cancellation: {e}")

        return rail_results

def route_optimistic_execution(state: AgentState) -> Literal["governed_trader", "execution_analyst", "system_2_simulation"]:
    """
    Router determining if we proceed to the Write Action (Governed Trader)
    or fallback to replanning.
    """
    safety = state.get("safety_status")
    nemo = state.get("nemo_status")

    if safety == "UNCERTAIN":
        return "system_2_simulation"

    if (safety == "APPROVED" or safety == "SKIPPED") and \
       (nemo == "APPROVED" or nemo == "SKIPPED"):
        return "governed_trader"

    return "execution_analyst"
