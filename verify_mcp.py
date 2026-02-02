# Helper script to verifying MCP tool execution
# Simulating a client connecting to the server (Mocking the server process for unit testing logic)

import asyncio
from src.gateway.server.mcp_server import enforce_governance, execute_trade_action

async def test_mcp_logic():
    print("Testing MCP Logic...")

    # Test 1: Market Status (doesn't hit governance)
    # Skipped as it uses yfinance/real network.

    # Test 2: Governance Logic (Dry Run)
    print("Testing Governance (Dry Run)...")
    try:
        # Should pass dry run
        result = await execute_trade_action(
            symbol="AAPL",
            amount=10,
            currency="USD",
            dry_run=True
        )
        print(f"Result: {result}")
        if "DRY_RUN: APPROVED" in result:
             print("✅ Governance Logic Passed")
        else:
             print(f"❌ Governance Logic Unexpected: {result}")

    except Exception as e:
        print(f"❌ Governance Logic Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_mcp_logic())
