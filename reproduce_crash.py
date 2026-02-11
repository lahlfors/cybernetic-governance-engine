
import asyncio
import os
import sys
from dotenv import load_dotenv

# Load env
load_dotenv()

# Override for local testing with port-forward
os.environ["VLLM_REASONING_API_BASE"] = "http://127.0.0.1:8086/v1"
if "REDIS_URL" in os.environ:
    del os.environ["REDIS_URL"]
if "REDIS_HOST" in os.environ:
    del os.environ["REDIS_HOST"]

# Add src to path
sys.path.append(os.getcwd())

print(f"DEBUG: Pre-import VLLM_REASONING_API_BASE={os.environ.get('VLLM_REASONING_API_BASE')}")

from src.governed_financial_advisor.graph.graph import create_graph
from src.governed_financial_advisor.utils.telemetry import configure_telemetry

from config.settings import Config
print(f"DEBUG: Config.VLLM_REASONING_API_BASE={Config.VLLM_REASONING_API_BASE}")

async def reproduce():
    print("🚀 Starting reproduction script...")
    
    # 1. Initialize Graph
    # We use a memory checkpointer to rule out Redis issues first, 
    # unless we suspect Redis is the cause.
    # But server.py uses Config.REDIS_URL.
    # Let's try with MemorySaver first by passing None.
    print("Initializing Graph with MemorySaver...")
    graph = create_graph(redis_url=None)
    
    # 2. Invoke Graph with a prompt that triggers Execution Analyst (Strategy)
    # We simulate that Market Analysis is done or just ask for a strategy directly
    inputs = {
        "messages": [
            ("user", "User Profile Context: Risk Attitude: Conservative, Investment Period: Long Term.\nCreate a trading strategy for AAPL.")
        ]
    }
    print(f"invoking with prompt: '{inputs['messages'][0][1]}'")
    
    try:
        res = await graph.ainvoke(
            inputs,
            {"recursion_limit": 20, "configurable": {"thread_id": "test_thread"}}
        )
        print("✅ Graph passed!")
        if res and "messages" in res:
            if "execution_plan_output" in res and res["execution_plan_output"]:
                print("--- [Test] Plan Generated. Simulating User Approval... ---")
                approval_msg = "The strategy looks good. Please proceed with execution."
                
                res_exec = await graph.ainvoke(
                    {"messages": [("user", approval_msg)]},
                    {"recursion_limit": 20, "configurable": {"thread_id": "test_thread"}}
                )
                print("✅ Execution Phase Graph passed!")
                print(f"Final Response: {res_exec['messages'][-1].content}")
            else:
                print("⚠️ No execution plan found in state to approve.")
                print(f"Response: {res['messages'][-1].content}") # Original print for non-execution plan cases
    except Exception as e:
        print(f"❌ Graph failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(reproduce())
