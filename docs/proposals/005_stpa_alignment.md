# Proposal: Aligning Codebase with STPA Strategic Framework

## 1. Context & Motivation
The strategic framework "Implementing STAMP for AI Safety and Reliability" establishes a rigorous methodology for AI governance, moving beyond simple failure analysis to System-Theoretic Process Analysis (STPA).

Currently, the codebase implements the *mechanics* of this (risk checks, transpilers, safety nodes) but lacks the *semantic model* of STPA. Concepts like "Losses", "Hazards", "Control Loops", and "Process Model Flaws" are implicit or hardcoded in strings, rather than being first-class citizens in the code.

This proposal outlines the necessary refactoring to explicitly model the 4 STPA Steps within the codebase.

## 2. Proposed Artifacts (`src/governance/stpa.py`)

We propose creating a central module `src/governance/stpa.py` to define the STPA ontology.

### Step 1: Defining Losses and Hazards

Instead of hardcoding "H-1" or "L-2" in prompts, we will define them as enumerations to ensure traceability.

```python
from enum import Enum, auto
from pydantic import BaseModel, Field
from typing import List, Optional

class LossType(str, Enum):
    L1_LOSS_OF_LIFE = "L-1: Loss of life or injury"
    L2_ASSET_DAMAGE = "L-2: Loss of or damage to vehicle/asset"
    L3_ENV_DAMAGE = "L-3: Damage to objects outside the vehicle"
    L4_MISSION_LOSS = "L-4: Loss of mission"

class HazardType(str, Enum):
    H1_SEPARATION = "H-1: Violates minimum separation"
    H2_INTEGRITY = "H-2: Structural/Asset integrity lost"
    H3_TERRAIN = "H-3: Unsafe distance from terrain"
    # Financial Extensions
    H_FIN_INSOLVENCY = "H-FIN-1: Insolvency (Drawdown > Limit)"
    H_FIN_LIQUIDITY = "H-FIN-2: Liquidity Trap (Slippage)"
```

### Step 2: Modeling the Control Structure

We need to explicitly model *who* is controlling *what*. Currently, the `adapters.py` file implicitly defines a loop, but we should formalize it.

```python
class ComponentType(str, Enum):
    HUMAN_SUPERVISOR = "Human Supervisor"
    AI_CONTROLLER = "AI Controller"
    ACTUATOR = "Actuator"
    SENSOR = "Sensor"

class ControlLoop(BaseModel):
    """
    Metadata describing the STPA Control Loop context.
    """
    name: str = Field(..., description="Name of the loop, e.g., 'Trading Execution Loop'")
    controller: str = Field(..., description="The AI Agent (e.g., 'ExecutionAnalyst')")
    controlled_process: str = Field(..., description="The external system (e.g., 'Market/Exchange')")
    feedback_mechanism: str = Field(..., description="How the agent sees state (e.g., 'Market Data Feed')")
```

### Step 3: Formalizing UCAs (Unifying Definitions)

Currently, we have `ProposedUCA` (in `risk_analyst/agent.py`) and `STAMP_UCA` (in `evaluator_agent/ontology.py`). We will unify these into a single `UCA` model that strictly enforces the 4 failure modes.

```python
class UCAType(str, Enum):
    NOT_PROVIDED = "Not Providing Causes Hazard"
    PROVIDED = "Providing Causes Hazard"
    TIMING_WRONG = "Too Early / Too Late"
    STOPPED_TOO_SOON = "Stopped Too Soon / Lasted Too Long"

class ConstraintLogic(BaseModel):
    variable: str
    operator: str
    threshold: str
    condition: Optional[str]

class UCA(BaseModel):
    id: str = Field(..., description="Unique ID, e.g., 'UCA-1'")
    type: UCAType
    hazard: HazardType
    description: str
    # Logic for the Transpiler
    logic: Optional[ConstraintLogic] = None
    # Detection pattern for the Auditor
    trace_pattern: Optional[str] = None
```

### Step 4: Causal Factors (Process Model Flaws)

This is the missing link. We need to explain *why* a UCA might happen.

```python
class ProcessModelFlaw(BaseModel):
    """
    Represents a divergence between the Agent's belief and Reality.
    """
    believed_state: str = Field(..., description="What the Agent thought (e.g., 'Market is Stable')")
    actual_state: str = Field(..., description="What was true (e.g., 'Flash Crash in progress')")
    missing_feedback: Optional[str] = Field(None, description="What sensor data was missing?")
```

## 3. Refactoring Plan

### A. Update Risk Analyst (`src/agents/risk_analyst/agent.py`)

The `RiskAssessment` output schema should be updated to use the new `UCA` class and explicitly include `ProcessModelFlaw` analysis.

**Revised Prompt Strategy:**
> "Identify UCAs and for each, hypothesize a Process Model Flaw: Why would the agent believe this action is safe when it is not? (e.g., Latency masking true price)."

### B. Update Transpiler (`src/governance/transpiler.py`)

Refactor the `transpile_policy` function to accept the unified `UCA` object. The logic remains the same (generating Python/Rego), but the input contract becomes stricter and type-safe.

### C. Update Evaluator (`src/evaluator_agent/ontology.py`)

Deprecate the local `STAMP_UCA` dataclass and import the shared `UCA` model from `src/governance/stpa.py`. This ensures that the Red Team (Evaluator) and the Blue Team (Risk Analyst) are using the exact same definitions of safety.

## 4. Benefits

1.  **Traceability:** We can trace a line of code in the `SafetyNode` directly back to `H-FIN-1` and `L-2`.
2.  **Completeness:** By using the `UCAType` Enum, we force the Risk Analyst to consider all 4 failure modes, preventing "tunnel vision" on just one type of error.
3.  **Explainability:** Adding `ProcessModelFlaw` makes the risk report much more useful for human debugging (understanding the *why*, not just the *what*).
