import asyncio
from src.gateway.server.mcp_server import evaluate_policy

async def verify_evaluator_tools():
    print("Verifying MCP Evaluator Tools...")

    # Test evaluate_policy directly (mocking internal OPA call failure)
    # This verifies the MCP wrapper exists and is callable
    try:
        result = await evaluate_policy(action="test_action", description="Checking MCP Wrapper", dry_run=True)
        print(f"Policy Result: {result}")
        if "ERROR" in result or "APPROVED" in result or "DENIED" in result:
             print("✅ evaluate_policy tool is active")
    except Exception as e:
        print(f"❌ evaluate_policy tool failed: {e}")

if __name__ == "__main__":
    asyncio.run(verify_evaluator_tools())
