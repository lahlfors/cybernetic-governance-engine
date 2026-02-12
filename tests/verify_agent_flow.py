
import requests
import json
import uuid
import time
import os

BACKEND_URL = os.getenv("BACKEND_URL", "http://34.122.99.196")
SESSION_ID = str(uuid.uuid4())

def query_agent(prompt):
    url = f"{BACKEND_URL}/agent/query"
    payload = {
        "prompt": prompt,
        "user_id": "test_user",
        "thread_id": SESSION_ID
    }
    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()["response"]
    except Exception as e:
        print(f"❌ Error querying agent: {e}")
        return ""

def test_agent_flow():
    print(f"🧪 Testing Agent Flow against {BACKEND_URL} (Session: {SESSION_ID})")
    
    # 1. Ticker First Check
    print("\n[Step 1] Initial Greeting (Expected: Ask for Ticker)")
    r1 = query_agent("Hello, I want a strategy.")
    print(f"🤖 Agent: {r1}")
    if "ticker" in r1.lower() or "stock" in r1.lower():
        print("✅ PASS: Agent asked for ticker.")
    else:
        print("❌ FAIL: Agent did not ask for ticker.")

    # 2. Market Analysis & Profile Check
    print("\n[Step 2] Providing Ticker (Expected: Analysis + Ask for Profile)")
    r2 = query_agent("Analyze AAPL")
    print(f"🤖 Agent: {r2[:100]}...")
    if "Risk Attitude" in r2 or "Risk Tolerance" in r2:
         print("✅ PASS: Agent asked for Risk Profile.")
    else:
         print("❌ FAIL: Agent did not ask for profile.")

    # 3. Strategy Generation
    print("\n[Step 3] Providing Profile (Expected: Strategy + Execution Offer)")
    r3 = query_agent("Aggressive, Long Term")
    print(f"🤖 Agent: {r3[:200]}...")
    if "Executive Plan" in r3 or "Strategy" in r3:
        print("✅ PASS: Agent generated a plan.")
    else:
        print("❌ FAIL: Agent did not generate a plan.")
        
    if "execute this trade" in r3:
        print("✅ PASS: Agent offered execution.")
    else:
        print("❌ FAIL: Agent did not offer execution.")

    # 4. High Risk Feedback (Simulation) - This is harder to trigger deterministically without specific params
    # But we can try a clearly unsafe request if we knew one.
    # For now, we verify the flow up to here.

if __name__ == "__main__":
    test_agent_flow()
