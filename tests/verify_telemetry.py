import asyncio
import sys
import os
import time
from unittest.mock import AsyncMock, MagicMock

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.governed_financial_advisor.governance.client import governed_tool, opa_client

# Mock dependencies
opa_client.evaluate_policy = AsyncMock(return_value="ALLOW")
opa_client.cb.is_bankrupt = MagicMock(return_value=False)

# Dummy Tool using Pydantic
from pydantic import BaseModel

class TradeAction(BaseModel):
    symbol: str
    amount: int

@governed_tool(action_name="test_trade", policy_id="test_policy")
async def execute_trade(action: TradeAction):
    print(">>> Executing Trade Logic...")
    await asyncio.sleep(0.1) # Simulate reasoning
    return "Trade Executed"

async def main():
    print("--- Starting Telemetry Verification ---")
    
    action = TradeAction(symbol="AAPL", amount=100)
    
    try:
        start = time.perf_counter()
        result = await execute_trade(action=action)
        duration = (time.perf_counter() - start) * 1000
        print(f"Result: {result}")
        print(f"Total Duration: {duration:.2f}ms")
        print("✅ Governance Tax & Reasoning Spend logic executed without error.")
        
    except Exception as e:
        print(f"❌ Verification Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
