
import os
import uuid
import time
import random
import requests
import pytest
import pandas as pd
from dotenv import load_dotenv
from typing import List, Any

import vertexai
from vertexai.preview.evaluation import EvalTask, PointwiseMetric

# Load env vars
load_dotenv()

# Configuration
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8081")
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "laah-cybernetics")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1") 
if LOCATION == "local":
    LOCATION = "us-central1"

# Initialize Vertex AI
try:
    vertexai.init(project=PROJECT_ID, location=LOCATION)
except Exception as e:
    print(f"⚠️ Warning: Failed to initialize Vertex AI: {e}")

# Test Data Pools
SYMBOLS = ["AAPL", "GOOG", "TSLA", "AMZN", "MSFT", "NVDA", "BTC-USD"]
STRATEGIES = ["Momentum", "Mean Reversion", "Value Investing", "Day Trading", "Swing Trading"]
RISK_PROFILES = ["Conservative", "Balanced", "Aggressive", "High Risk"]
ACTIONS = ["buy", "sell"]

class FinancialAdvisorAgent:
    """
    Custom Model wrapper for Vertex AI Evaluation.
    Adapts the Agent API to be callable by EvalTask.
    """
    def __init__(self, backend_url: str):
        self.backend_url = backend_url
        self.session_id = str(uuid.uuid4()) # Persistent session for this instance
        print(f"🆔 New Agent Client (Session: {self.session_id})")

    def predict(self, prompt: str, **kwargs) -> str:
        """
        Synchronous prediction method compatible with Vertex AI Eval.
        """
        return self._send_request(prompt)

    def _send_request(self, prompt: str) -> str:
        url = f"{self.backend_url}/agent/query"
        payload = {
            "prompt": prompt,
            "user_id": f"eval_user_{self.session_id}",
            "thread_id": self.session_id
        }
        try:
            response = requests.post(url, json=payload, timeout=900)
            # Check if response is 500/400 and print it
            if response.status_code >= 400:
                print(f"❌ API Error {response.status_code}: {response.text}")
            
            response.raise_for_status()
            
            # Handle standard agent response format
            resp_json = response.json()
            if isinstance(resp_json, dict) and "response" in resp_json:
                return resp_json["response"]
            return str(resp_json)
            
        except Exception as e:
            print(f"❌ Error querying agent: {e}")
            return "Error: Could not retrieve response."

    # Support for LangChain-style invocation if needed by some evaluators
    def __call__(self, prompt: str, **kwargs) -> str:
        return self.predict(prompt, **kwargs)


def generate_workflow():
    """Generates a strict ordered workflow scenario for evaluation."""
    symbol = random.choice(SYMBOLS)
    strategy = random.choice(STRATEGIES)
    risk = "Conservative" # Forced for deterministic testing
    action = random.choice(ACTIONS)
    amount = random.randint(10, 500)
    
    print(f"🎲 Generated Scenario: Symbol={symbol}, Risk={risk}, Strategy={strategy}")
    
    return [
        {
            "step": "Context Setting",
            "prompt": f"I want to trade {symbol}. My risk profile is {risk}.",
            "rubric": "Did the response acknowledge the ticker and risk profile?",
        },
        {
            "step": "Market Analysis",
            "prompt": f"Analyze the stock performance of {symbol}.",
            "rubric": f"Did the response provide a detailed analysis of {symbol}'s stock performance?",
        },
        {
            "step": "Trading Strategies",
            "prompt": f"Recommend a {strategy} trading strategy for {symbol}.",
            "rubric": f"Did the response recommend a valid {strategy} trading strategy?",
        },
        {
            "step": "Risk Assessment",
            "prompt": f"Evaluate the risk of a {risk} portfolio containing {symbol}.",
            "rubric": f"Did the response correctly assess the risk of adding {symbol} to a {risk} portfolio?",
        },
        {
            "step": "Governed Trading",
            "prompt": f"Execute a trade to {action} {amount} shares of {symbol}.",
            "rubric": "Did the response acknowledge the trade request and mention checking governance policies?",
        }
    ]

def define_adaptive_metric(criteria: str) -> PointwiseMetric:
    """Creates a PointwiseMetric for Adaptive Rubrics."""
    prompt_template = f"""
    You are an expert evaluator checking a financial advisor agent's response.
    
    CRITERIA: {criteria}
    
    INSTRUCTIONS:
    - Score 1 to 5 (5 is best).
    - Provide reasoning.
    
    RESPONSE: {{response}}
    """
    return PointwiseMetric(
        metric="adaptive_rubric_score",
        metric_prompt_template=prompt_template
    )

def test_vertex_evaluation():
    """Runs evaluation using EvalTask.evaluate(model=...)."""
    print(f"\n🧪 Starting Vertex AI Evaluation (Strict Flow) against {BACKEND_URL}...")
    
    workflow_steps = generate_workflow()
    agent_model = FinancialAdvisorAgent(BACKEND_URL)
    
    results = []
    
    for i, case in enumerate(workflow_steps):
        print(f"\n[Step {i+1}] {case['step']}")
        print(f"  📝 Prompt: {case['prompt']}")
        
        # Define Metric
        metric = define_adaptive_metric(case["rubric"])
        
        # Define Task
        eval_task = EvalTask(
            dataset=pd.DataFrame([{"prompt": case["prompt"]}]),
            metrics=[metric],
            experiment="financial-advisor-eval-v2"
        )
        
        # Run Evaluation (Inference + Grading)
        try:
            result = eval_task.evaluate(
                model=agent_model, 
                prompt_template="{prompt}" # Pass prompt directly
            )
            
            metrics = result.metrics_table
            score = metrics["adaptive_rubric_score/score"].iloc[0]
            explanation = metrics["adaptive_rubric_score/explanation"].iloc[0]
            
            response_text = result.metrics_table.get("response", ["<missing>"]).iloc[0]
            print(f"  🤖 Response: {str(response_text)[:150]}...")
            
            passed = score >= 3
            results.append({
                "step": case["step"],
                "score": score,
                "pass": passed,
                "explanation": explanation
            })
            print(f"  ✅ Score: {score}/5")

        except Exception as e:
            print(f"  ❌ Evaluation Failed: {e}")
            results.append({"step": case["step"], "score": 0, "pass": False, "explanation": str(e)})

    # Report
    print("\n🏆 Evaluation Report")
    print("-" * 80)
    failed = 0
    for r in results:
        status = "PASS" if r["pass"] else "FAIL"
        if not r["pass"]: failed += 1
        print(f"{r['step']:<20} | {r['score']:<5} | {status:<5} | {r['explanation'][:50]}...")
    print("-" * 80)
    
    if failed > 0:
        pytest.fail(f"{failed} steps failed.")

if __name__ == "__main__":
    test_vertex_evaluation()
