
import os
import uuid
import time
import random
import requests
import pytest
import pandas as pd
from dotenv import load_dotenv

import vertexai
from vertexai.preview.evaluation import EvalTask, PointwiseMetric, PointwiseMetricPromptTemplate

# Load env vars
load_dotenv()

# Configuration
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8081")
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "laah-cybernetics")
# Evaluation service is available in specific regions like us-central1
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1") 
if LOCATION == "local":
    LOCATION = "us-central1" # Force valid region for Eval Service even if app is local

# Initialize Vertex AI
try:
    vertexai.init(project=PROJECT_ID, location=LOCATION)
except Exception as e:
    print(f"⚠️ Warning: Failed to initialize Vertex AI: {e}")
    print("Ensure you have valid credentials and the API is enabled.")

# Test Data Pools
SYMBOLS = ["AAPL", "GOOG", "TSLA", "AMZN", "MSFT", "NVDA", "BTC-USD"]
STRATEGIES = ["Momentum", "Mean Reversion", "Value Investing", "Day Trading", "Swing Trading"]
RISK_PROFILES = ["Conservative", "Balanced", "Aggressive", "High Risk"]
ACTIONS = ["buy", "sell"]

def generate_workflow():
    """Generates a random workflow scenario for evaluation."""
    symbol = random.choice(SYMBOLS)
    strategy = random.choice(STRATEGIES)
    risk = random.choice(RISK_PROFILES)
    action = random.choice(ACTIONS)
    amount = random.randint(10, 500)
    
    return [
        {
            "step": "Market Analysis",
            "prompt": f"Analyze the stock performance of {symbol}.",
            "rubric": f"Did the response provide a detailed analysis of {symbol}'s stock performance, including current price trends and key financial indicators?",
        },
        {
            "step": "Trading Strategies",
            "prompt": f"Recommend a {strategy} trading strategy.",
            "rubric": f"Did the response recommend a valid {strategy} trading strategy and explain its mechanics and suitability?",
        },
        {
            "step": "Risk Assessment",
            "prompt": f"Evaluate the risk of a {risk} portfolio containing {symbol}.",
            "rubric": f"Did the response correctly assess the risk of adding {symbol} to a {risk} portfolio, mentioning volatility and diversification?",
        },
        {
            "step": "Governed Trading",
            "prompt": f"Execute a trade to {action} {amount} shares of {symbol}.",
            "rubric": "Did the response acknowledge the trade request and mention checking governance policies (like approval tokens, slippage, or limits) before execution?",
        }
    ]

def query_agent(prompt: str, session_id: str):
    """Sends a query to the agent backend."""
    url = f"{BACKEND_URL}/agent/query"
    payload = {
        "prompt": prompt,
        "user_id": "eval_user",
        "thread_id": session_id
    }
    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        return response.json().get("response", "")
    except Exception as e:
        print(f"❌ Error querying agent: {e}")
        return ""

def define_adaptive_metric(criteria: str) -> PointwiseMetric:
    """Creates a PointwiseMetric for Adaptive Rubrics using a custom prompt."""
    # Define a custom prompt template that incorporates the specific criteria
    # We use {{response}} to escape the placeholder for the actual response to be evaluated
    prompt_template = f"""
    You are an expert evaluator checking a financial advisor agent's response.
    
    CRITERIA TO EVALUATE:
    {criteria}
    
    INSTRUCTIONS:
    - Evaluate the response solely based on the criteria above.
    - Provide a score from 1 to 5, where 5 is perfectly aligned.
    - Provide a brief explanation of your reasoning.
    
    RESPONSE TO EVALUATE:
    {{response}}
    """
    
    return PointwiseMetric(
        metric="adaptive_rubric_score",
        metric_prompt_template=prompt_template
    )

def test_vertex_evaluation():
    """Runs the workflow and evaluates responses using Vertex AI."""
    print(f"\n🧪 Starting Vertex AI Evaluation against {BACKEND_URL}...")
    print(f"🌍 Project: {PROJECT_ID} | Region: {LOCATION}")

    workflow_steps = generate_workflow()
    
    # Generate a single session ID for the entire conversation
    session_id = str(uuid.uuid4())
    print(f"🆔 Session ID: {session_id}")
    
    eval_dataset = []
    
    # 1. Collect Responses, handling Multi-Turn Interactions
    for i, case in enumerate(workflow_steps):
        print(f"\n[Step {i+1}] {case['step']}")
        print(f"  Prompt: {case['prompt']}")
        
        # Pass the same session_id to maintain context
        response = query_agent(case['prompt'], session_id)
        
        # Interaction Loop (Handle Ticker and Profile requests)
        max_turns = 5
        for _ in range(max_turns):
            if "Risk Tolerance" in response and "Time Frame" in response:
                print(f"  ⚠️ Agent requested profile. Providing context...")
                context_response = "Risk Tolerance: Moderate, Time Frame: Medium-Term"
                if "Conservative" in case['prompt']:
                    context_response = "Risk Tolerance: Conservative, Time Frame: Long-Term"
                elif "Aggressive" in case['prompt']:
                     context_response = "Risk Tolerance: Aggressive, Time Frame: Short-Term"
            
                print(f"  ➡️ User Follow-up: {context_response}")
                response = query_agent(context_response, session_id)
                continue

            elif "Which stock ticker" in response or "stock ticker" in response:
                print(f"  ⚠️ Agent requested Ticker. Providing context...")
                symbol = "AAPL" # Default
                for s in SYMBOLS:
                    if s in case['prompt']:
                        symbol = s
                        break
            
                context_response = f"The ticker is {symbol}"
                print(f"  ➡️ User Follow-up: {context_response}")
                response = query_agent(context_response, session_id)
                continue
            
            # If no interactive prompt found, break loop (we have the final answer)
            break

        print(f"  Response ({len(response)} chars): {response[:100]}...")
        
        eval_dataset.append({
            "prompt": case['prompt'],
            "response": response,
            "rubric": case["rubric"],
            "step": case["step"]
        })

    # 2. Evaluate with Vertex AI
    print("\n⚖️  Running Vertex AI Evaluation (Adaptive Rubrics)...")
    
    results = []
    
    for item in eval_dataset:
        rubric = item["rubric"]
        prompt = item["prompt"]
        response = item["response"]
        
        # Define the metric dynamically for this item
        adaptive_metric = define_adaptive_metric(rubric)
        
        try:
            # Create a localized task for this single item
            # In a real pipeline, we'd batch items by rubric or use a generic "helpfulness" metric
            # But Adaptive Rubrics are specific to the prompt.
            eval_task = EvalTask(
                dataset=pd.DataFrame([{"prompt": prompt, "response": response}]),
                metrics=[adaptive_metric],
                experiment="financial-advisor-eval"
            )
            
            result = eval_task.evaluate()
            
            # Extract score and explanation
            # Extract score and explanation
            # API returns a RunMetrics object
            metrics_table = result.metrics_table
            try:
                score = metrics_table["adaptive_rubric_score/score"].iloc[0]
                explanation = metrics_table["adaptive_rubric_score/explanation"].iloc[0]
            except KeyError:
                print(f"  ⚠️ Warning: Metric key not found. Available columns: {metrics_table.columns.tolist()}")
                # Fallback or strict fail
                score = 0
                explanation = f"Metric missing. Columns: {metrics_table.columns.tolist()}"
            
            results.append({
                "step": item["step"],
                "score": score,
                "explanation": explanation,
                "pass": score >= 3 # Assuming 1-5 scale, 3+ is passing
            })
            print(f"  ✅ {item['step']}: Score {score}/5")
            
        except Exception as e:
            print(f"  ❌ {item['step']}: Evaluation Failed ({e})")
            results.append({
                "step": item["step"],
                "score": 0,
                "explanation": str(e),
                "pass": False
            })

    # 3. Report
    print("\n🏆 Evaluation Report")
    print("-" * 80)
    print(f"{'Step':<20} | {'Score':<5} | {'Pass':<5} | {'Explanation'}")
    print("-" * 80)
    
    failed_count = 0
    for r in results:
        status = "PASS" if r["pass"] else "FAIL"
        if not r["pass"]: failed_count += 1
        
        # Truncate explanation
        expl = (r['explanation'][:60] + '...') if len(r['explanation']) > 75 else r['explanation']
        print(f"{r['step']:<20} | {r['score']:<5} | {status:<5} | {expl}")
        
    print("-" * 80)
    
    if failed_count > 0:
        pytest.fail(f"{failed_count} steps failed semantic evaluation.")

if __name__ == "__main__":
    test_vertex_evaluation()
