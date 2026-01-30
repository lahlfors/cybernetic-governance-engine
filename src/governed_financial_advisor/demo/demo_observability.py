import asyncio
import logging
import uuid
import sys
import os

# Ensure src is in pythonpath
sys.path.append(os.getcwd())

from src.governed_financial_advisor.graph.graph import create_graph
from src.governed_financial_advisor.utils.context import user_context
from src.governed_financial_advisor.utils.telemetry import configure_telemetry
from src.governed_financial_advisor.infrastructure.redis_client import redis_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ObservabilityDemo")

async def run_demo():
    print("🚀 Starting Observability Feature Demo...")
    
    # 1. Initialize Telemetry & Graph
    configure_telemetry()
    graph = create_graph(redis_url="redis://localhost:6379")
    
    # Reset Safety State for clean demo
    print("\n🧹 Resetting Safety State (Redis)...")
    redis_client.set("safety:current_cash", "100000.0")
    
    # --- Scenario 1: Happy Path (Currency Ledger) ---
    print("\n--- Scenario 1: Happy Path (Generating 'Reasoning Spend') ---")
    print("Action: Junior Trader buys $1,000 AAPL")
    user_id = "demo_user_happy"
    thread_id = str(uuid.uuid4())
    
    token = user_context.set(user_id)
    try:
        # We invoke the graph with a prompt that triggers the tool
        # The LLM will call propose_trade -> execute_trade
        # We need to force it or phrase it clearly.
        # Note: The agent flow is complex. For this demo, we can just simulate the tool call 
        # OR invoke the agent. Invoking the agent is better for full trace.
        
        prompt = "I am a junior trader. Please buy 1000 USD of AAPL immediately."
        response = await graph.ainvoke(
            {"messages": [("user", prompt)]},
            config={"configurable": {"thread_id": thread_id}}
        )
        print(f"✅ Agent Response: {response['messages'][-1].content}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        user_context.reset(token)

    # --- Scenario 2: Policy Violation (Wall Impact) ---
    print("\n--- Scenario 2: Policy Violation (Generating 'Policy Friction') ---")
    print("Action: Junior Trader tries to buy $20,000 TSLA (Limit is $5,000)")
    user_id = "demo_user_risky"
    thread_id = str(uuid.uuid4())
    
    token = user_context.set(user_id)
    try:
        prompt = "I am a junior trader. Buy 20000 USD of TSLA."
        response = await graph.ainvoke(
            {"messages": [("user", prompt)]},
            config={"configurable": {"thread_id": thread_id}}
        )
        print(f"✅ Agent Response: {response['messages'][-1].content}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        user_context.reset(token)

    # --- Scenario 3: Bankruptcy (Bankruptcy Monitor) ---
    print("\n--- Scenario 3: Bankruptcy Protocol (Generating 'Bankruptcy Events') ---")
    print("Action: Draining the budget with repeated $4,500 trades until cash < $1,000")
    
    user_id = "demo_user_spender"
    thread_id = str(uuid.uuid4())
    token = user_context.set(user_id)
    
    try:
        # Loop to drain budget
        # Initial: 100k. Trade: 4.5k.
        # 22 trades * 4.5k = 99k. Remaining: 1k.
        # Next trade triggers bankruptcy.
        
        for i in range(25):
            print(f"\n💸 Trade #{i+1}: Buying $4,500 GOOGL...")
            prompt = f"I am a junior trader. Buy 4500 USD of GOOGL. Batch {i}."
            
            # Note: We use a unique thread per request or same thread? 
            # Same thread might have history context window issues if too long.
            # Let's use same thread to simulate a session, but ignore history buffer for now.
            
            response = await graph.ainvoke(
                {"messages": [("user", prompt)]},
                config={"configurable": {"thread_id": thread_id}}
            )
            print(f"Result: {response['messages'][-1].content}")
            
            # Check if we hit the wall
            if "UNSAFE" in str(response['messages'][-1].content) or "Bankruptcy" in str(response['messages'][-1].content):
                print("🚨 Bankruptcy Event Triggered!")
                break
                
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        user_context.reset(token)

    print("\n✅ Demo Complete! Check Langfuse Dashboard.")

if __name__ == "__main__":
    asyncio.run(run_demo())
