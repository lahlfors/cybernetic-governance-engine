import logging
import time
from typing import Dict, Any, Literal
from concurrent.futures import ThreadPoolExecutor
from src.graph.state import AgentState
from src.graph.nodes.safety_node import safety_check_node

logger = logging.getLogger("OptimisticExecution")

def trader_prep_node(state: AgentState) -> Dict[str, Any]:
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

    # Simulate API Latency for Market Data (Read-Only Tool)
    # In a real system, this would call `get_market_data(symbol)`
    time.sleep(0.1)

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

def optimistic_execution_node(state: AgentState) -> Dict[str, Any]:
    """
    Wrapper Node that executes Safety Check and Trader Prep in PARALLEL.
    Demonstrates Optimistic Execution pattern (Governance Budget).
    """
    logger.info("⚡ Optimistic Execution: Forking Safety and Prep Threads")

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_safety = executor.submit(safety_check_node, state)
        future_prep = executor.submit(trader_prep_node, state)

        # Wait for both (Barrier)
        result_safety = future_safety.result()
        result_prep = future_prep.result()

    logger.info("⚡ Optimistic Execution: Joined Threads. Proceeding to Gate.")

    # Merge results
    merged_update = {**result_safety, **result_prep}
    return merged_update

def route_optimistic_execution(state: AgentState) -> Literal["governed_trader", "execution_analyst"]:
    """
    Router determining if we proceed to the Write Action (Governed Trader)
    or fallback to replanning.
    """
    safety = state.get("safety_status")

    if safety == "APPROVED" or safety == "SKIPPED":
        return "governed_trader"

    return "execution_analyst"
