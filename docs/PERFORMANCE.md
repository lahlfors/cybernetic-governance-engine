# Performance Testing

This document outlines the performance measurement functionality for the Cybernetic Governance Engine Agent.

## Overview

We use a dedicated script `tests/test_agent_performance.py` to benchmark the agent's end-to-end performance. This script simulates real user interactions following a specific workflow and captures key latency and reliability metrics.

## Metrics Defined

The following metrics are captured for each request and aggregated by workflow step:

### 1. Time to First Token (TTFT)
- **Definition**: The latency from the moment the request is sent until the first byte/character of the response is received.
- **Importance**: Measures the perceived responsiveness of the agent. High TTFT indicates slow model inference start or high system overhead (guardrails, routing).

### 2. Total Turn Latency
- **Definition**: The total time taken for the full request-response cycle, from sending the request to receiving the complete response.
- **Importance**: Measures the overall speed of the system, including full generation time.

### 3. Error Rate
- **Definition**: The percentage of requests that result in a non-200 OK status code (e.g., 500 Internal Server Error, 403 Forbidden).
- **Importance**: Measures the reliability and stability of the system under load.

## Running the Benchmark

### Prerequisites
1. Ensure the Backend Service is running and accessible (via proxy or direct IP).
2. Install dependencies: `pip install requests`

### Command
```bash
# General Usage
python3 tests/test_agent_performance.py --url <BACKEND_URL> --iterations <N>

# Example (Local Proxy)
python3 tests/test_agent_performance.py --url http://localhost:8081 --iterations 5
```

### Scripts
- `tests/test_agent_performance.py`: The main performance benchmarking script.
- `scripts/proxy_backend.sh`: Helper script to port-forward the backend service to `localhost:8081`.

## Benchmark Workflow

The script executes a randomized 4-step workflow to simulate a realistic user session:
1.  **Market Analysis**: Checks stock performance.
2.  **Trading Strategies**: Requests strategy recommendations.
3.  **Risk Assessment**: Evaluates portfolio risk.
4.  **Governed Trading**: Attempts to execute a trade (triggering governance checks).

## Output

The script outputs a summary table:

```text
🏆 Performance metrics
--------------------------------------------------------------------------------------------------------------
Step Name            | Reqs  | Err%   | Avg TTFT   | P95 TTFT   | Avg Total  | P95 Total 
--------------------------------------------------------------------------------------------------------------
Market Analysis      | 5     | 0.0    | 0.450      | 0.520      | 2.100      | 2.500     
Trading Strategies   | 5     | 0.0    | 0.460      | 0.510      | 3.200      | 3.800     
...
```

## Advanced Evaluation (Vertex AI)

To further enhance accuracy measurement, the system includes a dedicated script `tests/test_vertex_evaluation.py` that integrates with **Vertex AI Gen AI Evaluation Service**.

### 1. Adaptive Rubrics (Test-Driven Evaluation)
Unlike keyword matching, this script uses **Adaptive Rubrics**:
- Automatically generates specific pass/fail criteria for *each* unique prompt.
- Uses a model-based judge to evaluate the response against these specific rubrics.
- **Benefit**: Transforms "vague" chat evaluation into **deterministic, engineering-grade unit tests** for semantic content.

### 2. Usage
```bash
# Requires Google Cloud Credentials
uv run python3 tests/test_vertex_evaluation.py
```
