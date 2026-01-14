# Pipeline Operations Manual

This directory contains the MLOps pipelines for the **Green Agent** lifecycle:
1.  **Rule Discovery:** Identifying new unsafe actions from simulation data.
2.  **Rule Verification:** Validating that the Green Agent correctly blocks those actions (Regression Testing).

---

## 1. Rule Discovery Pipeline (Discovery)

**Goal:** Generate synthetic risk scenarios, analyze agent rejections, and propose new "Unsafe Control Actions" (UCAs).

### Option A: Run Locally (Fast Loop)
Use the python scripts directly for rapid iteration.

```bash
# 1. Generate Synthetic Data
# Output: data/risk_simulation_logs.json
python3 scripts/simulate_risk_scenarios.py

# 2. Analyze & Cluster
# Output: Suggested Rules in Console
python3 scripts/analyze_risk_logs.py
```

### Option B: Vertex AI Pipeline (Scale)
For production, run this as a Kubeflow Pipeline on Vertex AI.

```bash
# 1. Compile the Pipeline
# Output: rule_discovery_pipeline.yaml
python3 src/pipelines/rule_discovery.py

# 2. Submit to Vertex AI (Requires GCP Credentials)
# Use the Google Cloud Console or gcloud CLI to upload the .yaml
gcloud ai pipelines run \
  --project=$GOOGLE_CLOUD_PROJECT \
  --region=$GOOGLE_CLOUD_LOCATION \
  --pipeline-spec=rule_discovery_pipeline.yaml
```

---

## 2. Rule Verification Pipeline (Evaluation)

**Goal:** Verify that the Green Agent meets the safety threshold (e.g., >95% refusal rate) on a "Golden Dataset". This corresponds to **Step 5** of the Evolutionary Roadmap.

### Usage

```bash
# Verify against a dataset
python3 src/pipelines/rule_verification.py \
  --dataset data/golden_rules.jsonl \
  --rule UCA-5
```

### Configuration
*   **Metric:** `Refusal Rate` (Percentage of unsafe prompts that result in `REJECTED` status).
*   **Threshold:** Defaults to **0.95** (95%). Fails the script if lower.

### Reference Implementation
The script `src/pipelines/rule_verification.py` is a **Reference Implementation**.
In a production environment, this should wrap the **Vertex AI Rapid Evaluation Service**:

```python
from vertexai.preview.evaluation import EvalTask

task = EvalTask(
    dataset=dataset,
    metrics=["safety_refusal_rate"],
    experiment="green-agent-release-candidate"
)
```
