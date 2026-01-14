"""
Vertex AI Pipeline Definition: Rule Discovery
This pipeline automates the generation of synthetic risk data and the identification of new unsafe control actions (UCAs).

Requirements:
    - kfp
    - google-cloud-aiplatform
"""

from typing import NamedTuple
from kfp import dsl
from kfp.dsl import (
    component,
    Input,
    Output,
    Dataset,
    Artifact,
    Metrics
)

# --------------------------------------------------------------------------------
# Component 1: Log Simulation
# --------------------------------------------------------------------------------
@component(
    base_image="python:3.10",
    packages_to_install=["pydantic"]
)
def generate_risk_logs(
    scenario_count: int,
    output_dataset: Output[Dataset]
):
    import json
    import random
    import uuid

    # (Simplified logic from scripts/simulate_risk_scenarios.py for portability)
    logs = []
    unsafe_pool = ["Max Leverage", "No Stop Loss", "Single Asset Concentration", "Regulatory: Wash Trade"]

    for _ in range(scenario_count):
        is_risky = random.random() > 0.3
        verdict = "REJECT" if is_risky else "APPROVE"

        unsafe_actions = []
        if is_risky:
            unsafe_actions = random.sample(unsafe_pool, 1)

        log = {
            "trace_id": str(uuid.uuid4()),
            "risk_json": {
                "verdict": verdict,
                "detected_unsafe_actions": unsafe_actions,
                "reasoning_summary": "Simulated risk assessment."
            }
        }
        logs.append(log)

    with open(output_dataset.path, "w") as f:
        json.dump(logs, f)

# --------------------------------------------------------------------------------
# Component 2: Cluster Analysis & Rule Proposal
# --------------------------------------------------------------------------------
@component(
    base_image="python:3.10",
    packages_to_install=["collections"]
)
def propose_rules(
    logs_input: Input[Dataset],
    candidates_output: Output[Artifact],
    metrics: Output[Metrics]
):
    import json
    import collections

    with open(logs_input.path, "r") as f:
        logs = json.load(f)

    # 1. Filter Rejections
    rejections = [l for l in logs if l["risk_json"]["verdict"] == "REJECT"]

    # 2. Extract Unsafe Actions
    all_actions = []
    for r in rejections:
        actions = r["risk_json"].get("detected_unsafe_actions", [])
        all_actions.extend(actions)

    # 3. Frequency Analysis (Clustering Proxy)
    counter = collections.Counter(all_actions)

    # 4. Generate Proposals
    proposals = []
    for action, count in counter.most_common(5):
        metrics.log_metric(f"count_{action.replace(' ', '_')}", count)

        # Simple heuristic to define a candidate
        proposals.append({
            "suggested_rule_id": f"UCA-AUTO-{abs(hash(action)) % 1000}",
            "description": f"Frequent unsafe action detected: {action}",
            "trigger_keywords": [action.lower()],
            "frequency": count
        })

    with open(candidates_output.path, "w") as f:
        json.dump(proposals, f, indent=2)

# --------------------------------------------------------------------------------
# Pipeline Definition
# --------------------------------------------------------------------------------
@dsl.pipeline(
    name="green-agent-rule-discovery",
    description="Simulates agent traffic and proposes new safety rules."
)
def rule_discovery_pipeline(
    scenario_count: int = 100
):
    # Step 1: Generate Data
    gen_task = generate_risk_logs(
        scenario_count=scenario_count
    )

    # Step 2: Analyze & Propose
    # In a real setup, we might use a dedicated container image with 'analyze_risk_logs.py' included.
    analyze_task = propose_rules(
        logs_input=gen_task.outputs["output_dataset"]
    )

if __name__ == "__main__":
    from kfp import compiler
    compiler.Compiler().compile(
        pipeline_func=rule_discovery_pipeline,
        package_path="rule_discovery_pipeline.yaml"
    )
