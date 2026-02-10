import os
import time
import uuid
import random
import statistics
import requests
import argparse
from dotenv import load_dotenv

# Load env vars
load_dotenv()

# Configuration
DEFAULT_BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8081")

# Test Data Pools
SYMBOLS = ["AAPL", "GOOG", "TSLA", "AMZN", "MSFT", "NVDA", "BTC-USD"]
STRATEGIES = ["Momentum", "Mean Reversion", "Value Investing", "Day Trading", "Swing Trading"]
RISK_PROFILES = ["Conservative", "Balanced", "Aggressive", "High Risk"]
ACTIONS = ["buy", "sell"]

def generate_workflow_prompts():
    """Generates a random workflow set of prompts."""
    symbol = random.choice(SYMBOLS)
    strategy = random.choice(STRATEGIES)
    risk = random.choice(RISK_PROFILES)
    action = random.choice(ACTIONS)
    amount = random.randint(10, 500)
    
    return [
        {"name": "Market Analysis", "prompt": f"Analyze the stock performance of {symbol}."},
        {"name": "Trading Strategies", "prompt": f"Recommend a {strategy} trading strategy."},
        {"name": "Risk Assessment", "prompt": f"Evaluate the risk of a {risk} portfolio containing {symbol}."},
        {"name": "Governed Trading", "prompt": f"Execute a trade to {action} {amount} shares of {symbol}."}
    ]

class AgentPerformanceTest:
    def __init__(self, backend_url):
        self.backend_url = backend_url
        print(f"🔧 Initialized Performance Test for: {self.backend_url}")

    def run_query(self, prompt: str):
        user_id = str(uuid.uuid4())
        url = f"{self.backend_url}/agent/query"
        payload = {
            "prompt": prompt,
            "user_id": user_id
        }
        
        start_time = time.time()
        ttft = 0.0
        try:
            # Use stream=True to measure Time to First Byte (TTFT approximation)
            with requests.post(url, json=payload, timeout=120, stream=True) as response:
                ttft = time.time() - start_time
                # Read full content to complete the turn
                _ = response.content
                end_time = time.time()
            
            total_latency = end_time - start_time
            
            if response.status_code == 200:
                return {
                    "ttft": ttft,
                    "total_latency": total_latency,
                    "status": 200,
                    "success": True,
                    "error": None
                }
            else:
                return {
                    "ttft": ttft,
                    "total_latency": total_latency,
                    "status": response.status_code,
                    "success": False,
                    "error": f"HTTP {response.status_code}"
                }
        except Exception as e:
            return {
                "ttft": 0.0,
                "total_latency": time.time() - start_time,
                "status": 0,
                "success": False,
                "error": str(e)
            }

def run_performance_test(test_runner, iterations, mode="workflow"):
    print(f"\n🚀 Running Performance Test ({iterations} iterations)... Mode: {mode}")
    print(f"Metrics: TTFT (First Token/Byte), Total Turn Latency, Error Rate")
    
    results = {}
    
    # Init buckets
    keys = ["Market Analysis", "Trading Strategies", "Risk Assessment", "Governed Trading"] if mode == "workflow" else ["Single Prompt"]
    for k in keys:
        results[k] = []

    # Loop
    for i in range(iterations):
        print(f"\nIteration {i+1}/{iterations}")
        
        if mode == "workflow":
            workflow = generate_workflow_prompts()
            print(f"  [Randomized Scenario]: {workflow[0]['prompt'].split('of ')[-1]}")
            for step in workflow:
                print(f"  [{step['name']}]...", end="", flush=True)
                stats = test_runner.run_query(step["prompt"])
                if stats["success"]:
                    print(f" TTFT: {stats['ttft']:.3f}s | Total: {stats['total_latency']:.3f}s")
                    results[step["name"]].append(stats)
                else:
                    print(f" ❌ Failed ({stats['error']})")
                    results[step["name"]].append(stats) # Track failures too for error rate
        else:
            prompt = "What is the current price of AAPL?" # Default
            print(f"  [Query]...", end="", flush=True)
            stats = test_runner.run_query(prompt)
            if stats["success"]:
                 print(f" TTFT: {stats['ttft']:.3f}s | Total: {stats['total_latency']:.3f}s")
                 results["Single Prompt"].append(stats)
            else:
                 print(f" ❌ Failed ({stats['error']})")
                 results["Single Prompt"].append(stats)

    # Metrics Report
    print("\n🏆 Performance metrics")
    print("-" * 110)
    print(f"{'Step Name':<20} | {'Reqs':<5} | {'Err%':<6} | {'Avg TTFT':<10} | {'P95 TTFT':<10} | {'Avg Total':<10} | {'P95 Total':<10}")
    print("-" * 110)
    
    for k in keys:
        data = results[k]
        if not data:
            continue
            
        total_reqs = len(data)
        errors = [r for r in data if not r["success"]]
        error_rate = (len(errors) / total_reqs) * 100
        
        success_data = [r for r in data if r["success"]]
        
        if success_data:
            ttfts = [r["ttft"] for r in success_data]
            totals = [r["total_latency"] for r in success_data]
            
            avg_ttft = statistics.mean(ttfts)
            p95_ttft = statistics.quantiles(ttfts, n=20)[18] if len(ttfts) >= 20 else max(ttfts)
            
            avg_total = statistics.mean(totals)
            p95_total = statistics.quantiles(totals, n=20)[18] if len(totals) >= 20 else max(totals)
            
            print(f"{k:<20} | {total_reqs:<5} | {error_rate:<6.1f} | {avg_ttft:<10.3f} | {p95_ttft:<10.3f} | {avg_total:<10.3f} | {p95_total:<10.3f}")
        else:
            print(f"{k:<20} | {total_reqs:<5} | {error_rate:<6.1f} | {'N/A':<10} | {'N/A':<10} | {'N/A':<10} | {'N/A':<10}")
            
    print("-" * 110)

def main():
    parser = argparse.ArgumentParser(description="Agent Performance Benchmark")
    parser.add_argument("--url", default=DEFAULT_BACKEND_URL, help="Backend URL")
    parser.add_argument("--iterations", type=int, default=3, help="Number of full workflow loops")
    parser.add_argument("--mode", default="workflow", choices=["workflow", "single"], help="Test mode")
    
    args = parser.parse_args()
    
    tester = AgentPerformanceTest(args.url)
    run_performance_test(tester, args.iterations, args.mode)

if __name__ == "__main__":
    main()
