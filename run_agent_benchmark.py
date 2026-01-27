import os
import time
import json
import requests
try:
    from langfuse import observe
    from langfuse.openai import openai # Patch OpenAI client if used, or use standard
except ImportError:
    print("⚠️ Langfuse not found. Tracing will be disabled.")
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    openai = None
from openai import OpenAI

from dotenv import load_dotenv

# Load env vars from .env
load_dotenv()

# Configuration
VLLM_API_BASE = os.getenv("VLLM_API_BASE", "http://localhost:8000/v1") 
MODEL_NAME = os.getenv("VLLM_MODEL", "google/gemma-2-9b-it")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")

# Initialize Client
client = OpenAI(
    base_url=VLLM_API_BASE,
    api_key="EMPTY",
)

@observe(name="tool_execution")
def execute_tool(tool_name, args):
    """Simulates a tool call with network latency."""
    time.sleep(0.5) # Simulate RTT
    if tool_name == "calculator":
        return eval(args.get("expression", "0"))
    return "Tool not found"

    return "Tool not found"

@observe(name="governance_check")
def measure_governance_overhead(check_type="pre_flight"):
    """Simulates the overhead of NeMo Guardrails/OPA checks."""
    # Simulating latency for: check_approval_token, check_drawdown_limit, etc.
    time.sleep(0.15) # Example: 150ms governance latency
    return "SAFE"

@observe(name="agent_reasoning")
def run_agent_step(prompt):
    """Executes a single step of the agent: Model -> Tool -> Result."""
    
    """Executes a single step of the agent: Model -> Tool -> Result."""
    
    # 0. Pre-Generation Governance (Input Rails)
    measure_governance_overhead("input_rails")

    # 1. Model Inference (Reasoning)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=256
    )
    
    content = response.choices[0].message.content
    content = response.choices[0].message.content
    
    # 2. Post-Generation Governance (Output Rails)
    measure_governance_overhead("output_rails")

    # 3. Simulated Tool parsing (naive)
    if "CALC" in content:
        # Fictitious parsing logic
        result = execute_tool("calculator", {"expression": "2+2"})
        return f"{content}\nResult: {result}"
        
    return content

@observe(name="e2e_benchmark_task")
def run_benchmark_iteration(iteration_id):
    print(f"--- Starting Iteration {iteration_id} ---")
    start = time.time()
    
    response = run_agent_step("Calculate 2+2 and explain the philosophy of math.")
    
    duration = time.time() - start
    print(f"Iteration {iteration_id}: {duration:.2f}s")
    print(f"Output: {response[:50]}...")

if __name__ == "__main__":
    print("🚀 Starting E2E Agent Benchmark...")
    print(f"Targeting vLLM at: {VLLM_API_BASE}")
    print(f"Tracing to Langfuse at: {LANGFUSE_HOST}")
    
    # Warmup
    # run_benchmark_iteration(0)
    
    for i in range(1, 4):
        run_benchmark_iteration(i)
        time.sleep(1)
