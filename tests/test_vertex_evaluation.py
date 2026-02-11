
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
    """Generates a sequential workflow scenario for evaluation."""
    symbol = random.choice(SYMBOLS)
    strategy = random.choice(STRATEGIES)
    risk = random.choice(RISK_PROFILES)
    action = random.choice(ACTIONS)
    amount = random.randint(10, 500)
    
    # We must follow the strict dialogue flow expected by the Financial Coordinator
    return [
        {
            "step": "Market Analysis",
            "prompt": f"Hi, please analyze the stock performance of {symbol}.",
            "rubric": f"Did the response provide a detailed analysis of {symbol}'s stock performance?",
        },
        {
            "step": "Trading Strategies",
            # Provide context as requested by the prompt ("Input: ... check if user provided profile")
            "prompt": f"I have a {risk} risk profile and a long-term investment horizon. Based on the analysis, recommend a {strategy} trading strategy.",
            "rubric": f"Did the response recommend a {strategy} trading strategy suitable for a {risk} profile?",
        },
        {
            "step": "Execution Plan",
            "prompt": "That looks good. Please create a detailed Execution Plan for this strategy.",
            "rubric": "Did the response provide a concrete execution plan?",
        },
        {
            "step": "Governed Trading",
            # The prompt says: "If the user agrees to execute... you MUST route them..."
            "prompt": f"Yes, please proceed to execute the trade: {action} {amount} shares of {symbol}.",
            "rubric": "Did the response indicate that the trade is being executed or checked against governance policies?",
        }
    ]

def query_agent(prompt: str, user_id: str):
    """Sends a query to the agent using a persistent user_id."""
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
            data = response.json()
            # The agent returns a dict, likely with 'response' key
            # If the backend returns a raw string or different format, adjust here.
            return data.get("response", str(data))
        except requests.exceptions.RequestException as e:
            print(f"Request failed (Attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                return f"Error: Failed to get response from agent. {e}"

def define_adaptive_metric(criteria: str) -> PointwiseMetric:
    """Creates a PointwiseMetric for Adaptive Rubrics using a custom prompt."""
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
    
    # SINGLE SESSION for the entire workflow
    session_id = str(uuid.uuid4())
    print(f"🆔 Session ID: {session_id}")
    
    eval_dataset = []
    
    # 1. Collect Responses
    for i, case in enumerate(workflow_steps):
        print(f"\n[Step {i+1}] {case['step']}")
        print(f"  Prompt: {case['prompt']}")
        
        response = query_agent(case['prompt'], session_id)
        # Clean up response for display
        display_response = response.replace('\n', ' ')[:100]
        print(f"  Response: {display_response}...")
        
        eval_dataset.append({
            "prompt": case['prompt'],
            "response": response,
            "rubric": case["rubric"],
            "step": case["step"]
        })
        
        # Simple wait to ensure async state consistency if needed
        time.sleep(1)

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
            # API returns a RunMetrics object
            metrics_table = result.metrics_table
            score = metrics_table["adaptive_rubric_score"].iloc[0]
            explanation = metrics_table["adaptive_rubric_score_explanation"].iloc[0]
            
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
