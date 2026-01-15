# Evaluator Agent Subsystem (Layer 4: Verification)

The **Evaluator Agent** is the "Proctor" of the system. It is strictly separated from the runtime "Purple Agent" (Financial Coordinator). Its job is to Audit, Simulate, and Grade.

## Components

### 1. The Auditor (`auditor.py`)
The **EvaluatorAuditor** implements a "Neuro-Symbolic" evaluation approach suitable for Vertex AI Rapid Evaluation.
*   **Symbolic Layer:** Uses `logic.py` to check deterministic constraints against the structured `ExecutionPlan`.
*   **Neural Layer:** Uses an LLM Judge (simulated) to score the "Reasoning Trace" against a qualitative rubric.
*   **Reference Layer:** Generates a "Gold Standard" plan to compare against the agent's actual plan.

**Usage:**
```python
from src.evaluator_agent.auditor import evaluator_auditor
result = evaluator_auditor.audit_trace(trace_data)
print(result['safety_score']) # 0-100
```

### 2. The Ontology (`ontology.py`)
This is the **Source of Truth**. It defines the **STPA Unsafe Control Actions (UCAs)** that the system must avoid.
*   **UCA-1 to UCA-6:** Defined as `STAMP_UCA` dataclasses with `detection_pattern`.
*   Used by the Auditor to build the Grading Rubric.
*   Used by the Red Agent to target attacks.

### 3. AgentBeats Simulator (`simulator.py`)
Implements the "Agentified Evaluation" loop.
1.  **Setup:** Mocks the market environment.
2.  **Red Team:** `RedAgent` generates an attack (e.g., Prompt Injection targeting UCA-1).
3.  **Purple Agent:** The system under test attempts to handle the attack.
4.  **Grading:** The Evaluator Agent audits the interaction.

### 4. Red Agent (`red_agent.py`)
The Adversarial Agent. It does not just fuzz random inputs; it targets specific **STPA Hazards**.
*   *Attack Type:* "Context Overflow" -> Targets UCA-2 (Latency).
*   *Attack Type:* "Social Engineering" -> Targets UCA-3 (PII).
