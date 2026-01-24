import logging
import time
import asyncio
from typing import Dict, Any, Literal
from concurrent.futures import ThreadPoolExecutor
from src.graph.state import AgentState
from src.graph.nodes.safety_node import safety_check_node

logger = logging.getLogger("OptimisticExecution")

async def trader_prep_node(state: AgentState) -> Dict[str, Any]:
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

async def optimistic_execution_node(state: AgentState) -> Dict[str, Any]:
    """
    Wrapper Node that executes Safety Check and Trader Prep in PARALLEL.
    Demonstrates Optimistic Execution pattern (Governance Budget).
    """
    logger.info("⚡ Optimistic Execution: Forking Safety and Prep Threads")

    # 1. Start the Safety Check (The Gatekeeper)
    # safety_check_node is now async, so we just create a task
    rail_task = asyncio.create_task(safety_check_node(state))

    # 2. Start the Tool Execution (Optimistic)
    tool_task = asyncio.create_task(trader_prep_node(state))

    # 3. Wait for the Guardrail FIRST
    try:
        rail_result = await rail_task
    except Exception as e:
        logger.error(f"Safety check failed with exception: {e}")
        tool_task.cancel()
        return {"safety_status": "ERROR", "error": str(e)}

    # 4. Decide based on Guardrail result
    safety_status = rail_result.get("safety_status")

    if safety_status == "APPROVED" or safety_status == "SKIPPED":
        logger.info("✅ Safety Approved. Waiting for Tool Result...")
        try:
            # If allowed, retrieve the already-running tool result
            prep_result = await tool_task
            return {**rail_result, **prep_result}
        except asyncio.CancelledError:
             logger.warning("Tool task was cancelled unexpectedly.")
             return {**rail_result, "trader_prep_error": "Cancelled"}
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return {**rail_result, "trader_prep_error": str(e)}

    else:
        # If denied (BLOCKED/ESCALATED), cancel the tool task immediately
        logger.warning(f"⛔ Safety Status: {safety_status}. Cancelling Optimistic Tool.")
        tool_task.cancel()

        # Await the task to ensure cancellation cleanup completes (optional but good practice)
        try:
            await tool_task
        except asyncio.CancelledError:
            pass # Expected
        except Exception as e:
            logger.error(f"Error during tool cancellation: {e}")

        return rail_result

def route_optimistic_execution(state: AgentState) -> Literal["governed_trader", "execution_analyst"]:
    """
    Router determining if we proceed to the Write Action (Governed Trader)
    or fallback to replanning.
    """
    safety = state.get("safety_status")

    if safety == "APPROVED" or safety == "SKIPPED":
        return "governed_trader"

    return "execution_analyst"
