import os
import uuid
import time
import random
import requests
import pytest
from dotenv import load_dotenv

# Load env vars
load_dotenv()

# Configuration
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8081")

# Test Data Pools
SYMBOLS = ["AAPL", "GOOG", "TSLA", "AMZN", "MSFT", "NVDA", "BTC-USD"]
STRATEGIES = ["Momentum", "Mean Reversion", "Value Investing", "Day Trading", "Swing Trading"]
RISK_PROFILES = ["Conservative", "Balanced", "Aggressive", "High Risk"]
ACTIONS = ["buy", "sell"]

def generate_workflow():
    """Generates a random workflow scenario."""
    symbol = random.choice(SYMBOLS)
    strategy = random.choice(STRATEGIES)
    risk = random.choice(RISK_PROFILES)
    action = random.choice(ACTIONS)
    amount = random.randint(10, 500)
    
    return [
        {
            "step": "Market Analysis",
            "prompt": f"Analyze the stock performance of {symbol}.",
            "expected": ["price", "trend", "analysis", symbol],
            "type": "contains_any"
        },
        {
            "step": "Trading Strategies",
            "prompt": f"Recommend a {strategy} trading strategy.",
            "expected": ["strategy", "recommendation", strategy],
            "type": "contains_any"
        },
        {
            "step": "Risk Assessment",
            "prompt": f"Evaluate the risk of a {risk} portfolio containing {symbol}.",
            "expected": ["risk", "volatility", "assessment", risk],
            "type": "contains_any"
        },
        {
            "step": "Governed Trading",
            "prompt": f"Execute a trade to {action} {amount} shares of {symbol}.",
            "expected": ["policy", "check", "approved", "rejected", "governance"],
            "type": "contains_any"
        }
    ]

def query_agent(prompt: str):
    """Sends a query to the agent."""
    user_id = str(uuid.uuid4())
    url = f"{BACKEND_URL}/agent/query"
    payload = {
        "prompt": prompt,
        "user_id": user_id
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Request failed (Attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                return None

def test_agent_workflow_accuracy():
    """Runs the accuracy tests following the specific workflow."""
    print(f"\n🔍 Testing Agent Accuracy (Randomized Workflow) against {BACKEND_URL}...")
    
    # Generate a random workflow for this run
    workflow_steps = generate_workflow()
    
    passed = 0
    failed = 0
    
    for i, case in enumerate(workflow_steps):
        step_name = case["step"]
        prompt = case["prompt"]
        print(f"\nStep {i+1}: {step_name}")
        print(f"  Prompt: '{prompt}'")
        
        result = query_agent(prompt)
        
        if not result or "response" not in result:
            print("❌ FAIL: No valid response received.")
            failed += 1
            continue
            
        agent_response = result["response"]
        print(f"  Agent Response: {agent_response[:100].replace(chr(10), ' ')}...")
        
        # Validation Logic
        is_pass = False
        check_type = case.get("type", "contains")
        expected = case["expected"]
        
        if check_type == "contains":
            is_pass = expected.lower() in agent_response.lower()
        elif check_type == "contains_any":
             is_pass = any(x.lower() in agent_response.lower() for x in expected)
        elif check_type == "contains_all":
             is_pass = all(x.lower() in agent_response.lower() for x in expected)
        
        if is_pass:
            print("✅ PASS")
            passed += 1
        else:
            print(f"❌ FAIL: Expected keywords from {expected}")
            failed += 1
            
    print("-" * 30)
    print(f"Results: {passed} Passed, {failed} Failed")
    
    assert failed == 0, f"{failed} workflow steps failed."

if __name__ == "__main__":
    test_agent_workflow_accuracy()
