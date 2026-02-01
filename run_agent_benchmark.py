import os
import time
import json
import argparse
import random
from abc import ABC, abstractmethod
from dotenv import load_dotenv

# Load env vars from .env
load_dotenv()

try:
    from langfuse import observe
    # from langfuse.openai import openai # Patch OpenAI client if used, or use standard
except ImportError:
    # print("⚠️ Langfuse not found. Tracing will be disabled.")
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

from openai import OpenAI

# Configuration
VLLM_API_BASE = os.getenv("VLLM_API_BASE", "http://localhost:8000/v1") 
MODEL_NAME = os.getenv("VLLM_MODEL", "google/gemma-2-9b-it")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")

class ModelBackend(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        pass

class VLLMBackend(ModelBackend):
    def __init__(self, base_url, model_name):
        self.client = OpenAI(base_url=base_url, api_key="EMPTY")
        self.model_name = model_name

    def generate(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=256
        )
        return response.choices[0].message.content

class SimulatedBackend(ModelBackend):
    def __init__(self, name, mean_latency, jitter=0.1):
        self.name = name
        self.mean_latency = mean_latency
        self.jitter = jitter

    def generate(self, prompt: str) -> str:
        # Simulate network/processing latency
        delay = self.mean_latency + random.uniform(-self.jitter, self.jitter)
        time.sleep(max(0, delay))
        return f"[{self.name}] Simulated response to: {prompt[:20]}..."

@observe(name="tool_execution")
def execute_tool(tool_name, args):
    """Simulates a tool call with network latency."""
    time.sleep(0.5) # Simulate RTT
    if tool_name == "calculator":
        return eval(args.get("expression", "0"))
    return "Tool not found"

@observe(name="governance_check")
def measure_governance_overhead(check_type="pre_flight"):
    """Simulates the overhead of NeMo Guardrails/OPA checks."""
    time.sleep(0.15) # Example: 150ms governance latency
    return "SAFE"

@observe(name="agent_reasoning")
def run_agent_step(backend: ModelBackend, prompt: str):
    """Executes a single step of the agent: Model -> Tool -> Result."""
    
    # 0. Pre-Generation Governance (Input Rails)
    measure_governance_overhead("input_rails")

    # 1. Model Inference (Reasoning)
    content = backend.generate(prompt)
    
    # 2. Post-Generation Governance (Output Rails)
    measure_governance_overhead("output_rails")

    # 3. Simulated Tool parsing (naive)
    # Force tool use for benchmark consistency if prompt asks for calculation
    if "Calculate" in prompt or "CALC" in content:
        # Fictitious parsing logic
        result = execute_tool("calculator", {"expression": "2+2"})
        return f"{content}\nResult: {result}"
        
    return content

@observe(name="e2e_benchmark_task")
def run_benchmark_iteration(iteration_id, backend: ModelBackend, prompt: str):
    start = time.time()
    response = run_agent_step(backend, prompt)
    duration = time.time() - start
    return duration, response

def run_scenario(name, backend, iterations=3):
    print(f"\n🚀 Running Scenario: {name}")
    durations = []
    for i in range(iterations):
        dur, _ = run_benchmark_iteration(i, backend, "Calculate 2+2 and explain the philosophy of math.")
        durations.append(dur)
        print(f"  Iteration {i+1}: {dur:.3f}s")
    
    avg_duration = sum(durations) / len(durations)
    print(f"  👉 Average Latency: {avg_duration:.3f}s")
    return avg_duration

def main():
    parser = argparse.ArgumentParser(description="Agent Performance Benchmark")
    parser.add_argument("--mode", choices=["vllm", "simulate", "comparison"], default="comparison")
    parser.add_argument("--vllm-url", default=VLLM_API_BASE)
    parser.add_argument("--iterations", type=int, default=3)
    args = parser.parse_args()

    if args.mode == "vllm":
        backend = VLLMBackend(args.vllm_url, MODEL_NAME)
        run_scenario("vLLM (Real)", backend, args.iterations)
    
    elif args.mode == "simulate":
        backend = SimulatedBackend("Simulated Generic", 1.0)
        run_scenario("Simulated", backend, args.iterations)

    elif args.mode == "comparison":
        print("📊 Running Comparative Analysis: Hybrid Gemini vs Only Llama (Simulated)")

        # Scenario A: Hybrid Gemini/Llama
        # Assumption: Gemini Pro (Reasoning) has higher latency (~1.5s) + standard overhead
        gemini_backend = SimulatedBackend("Gemini 1.5 Pro", mean_latency=1.5, jitter=0.2)
        latency_gemini = run_scenario("Hybrid Gemini/Llama Architecture", gemini_backend, args.iterations)

        # Scenario B: Only Llama
        # Assumption: Llama 3 70B (vLLM) has lower latency (~0.5s) + standard overhead
        llama_backend = SimulatedBackend("Llama 3 70B (vLLM)", mean_latency=0.5, jitter=0.1)
        latency_llama = run_scenario("Only Llama Architecture", llama_backend, args.iterations)

        print("\n🏆 Performance Summary")
        print("-" * 60)
        print(f"{'Architecture':<30} | {'Avg Latency':<12} | {'Throughput (est)':<15}")
        print("-" * 60)
        print(f"{'Hybrid Gemini/Llama':<30} | {latency_gemini:.3f}s       | {60/latency_gemini:.2f} RPM")
        print(f"{'Only Llama':<30} | {latency_llama:.3f}s       | {60/latency_llama:.2f} RPM")
        print("-" * 60)

        improvement = ((latency_gemini - latency_llama) / latency_gemini) * 100
        print(f"⚡ Llama Only is {improvement:.1f}% faster than Hybrid Gemini.")
        print("Note: Hybrid Gemini provides higher reasoning capability (Google ADK) at the cost of latency.")

if __name__ == "__main__":
    main()
