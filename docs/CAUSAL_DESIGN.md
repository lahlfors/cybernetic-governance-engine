# Causal Engine Software Design Document

## 1. Overview

This document defines the software architecture and design of the Causal Engine and Policy Induction subsystem within the Sovereign Stack. This subsystem provides two critical capabilities:

1.  **System 2 "Rational Fallback":** A runtime mechanism to evaluate high-risk actions when rule-based governance (OPA) returns `UNCERTAIN`.
2.  **Offline Policy Induction:** A pipeline to discover new safety rules by simulating counterfactual scenarios and converting them into OPA Rego policies.

The design targets Systems Engineers, focusing on component interactions, data flow, and integration with the broader governance architecture rather than the mathematical theory of Structural Causal Models (SCMs).

## 2. Architectural Principles

*   **Hybrid Intelligence:** Combines deterministic rules (System 1/OPA) for speed with probabilistic causal reasoning (System 2/DoWhy) for handling ambiguity.
*   **Separation of Training and Inference:** The causal model structure and mechanism weights are trained offline to produce a lightweight, binary artifact (`.pkl`) for efficient runtime loading.
*   **Safety as Code:** The output of the offline induction process is executable code (Rego), ensuring that discovered risks are enforced deterministically in future iterations.

## 3. System Components

The subsystem consists of three primary software modules:

### 3.1. Production Causal Engine (`src/causal/engine.py`)

This module is the runtime kernel of the subsystem. It wraps the `dowhy.gcm` library to provide a stable API for higher-level agents.

*   **Class:** `ProductionSCM`
*   **Responsibility:**
    *   Loads the serialized SCM artifact (`models/prod_scm_v1.pkl`).
    *   Provides a thread-safe method `simulate_intervention` to execute the "do-operator".
    *   Handles context mapping: Filters incoming application state (JSON) to match the nodes in the causal graph.
    *   Executes Monte Carlo simulations to estimate the probability of target outcomes (e.g., `Churn_Probability`).

### 3.2. Offline Training Pipeline (`scripts/train_causal_model.py`)

This script is responsible for constructing the "Physics" of the domain model.

*   **Responsibility:**
    *   **Graph Definition:** Explicitly defines the Directed Acyclic Graph (DAG) using `networkx` (e.g., `Transaction_Amount -> Fraud_Risk`).
    *   **Mechanism Assignment:** Maps edges to statistical models (e.g., Gradient Boosted Regressors, Additive Noise Models) that learn the functional relationships.
    *   **Synthetic Data Generation:** Generates bootstrap data to train the mechanisms in the absence of massive production datasets.
    *   **Artifact Generation:** Serializes the fitted SCM object into `models/prod_scm_v1.pkl`.

### 3.3. Policy Induction Engine (`scripts/causal_policy_induction.py`)

This module implements the "Safety Discovery" loop. It treats the trained SCM as a simulator to find hazardous boundaries.

*   **Responsibility:**
    *   **Search Strategy:** Iterates through variable spaces (e.g., `Tenure_Years` from 0 to 10) while holding other factors constant.
    *   **Intervention Simulation:** Systematically applies "Control Actions" (e.g., `Customer_Friction = 0.9` mimicking a BLOCK).
    *   **Violation Detection:** Checks if the outcome (e.g., `Churn_Probability`) exceeds safety thresholds defined in the configuration.
    *   **Code Generation:** Automatically writes OPA Rego rules (`policies/generated_causal_rules.rego`) to block actions that violate safety limits.

## 4. Data Flow

### 4.1. Runtime Execution Flow (System 2 Fallback)

This flow occurs when the `supervisor_node` routes an interaction to `system_2_simulation_node` because OPA returned `UNCERTAIN`.

1.  **Input:** The `system_2_simulation_node` receives the `AgentState`, containing `context` (user data) and a `proposed_action`.
2.  **Mapping:** The node maps the `proposed_action` to a specific causal intervention (e.g., "block_transaction" -> `Customer_Friction: 0.9`).
3.  **Inference:**
    *   `ProductionSCM` receives the `context` and `intervention`.
    *   It conditions the SCM on the `context`.
    *   It applies the intervention to the graph logic.
    *   It draws `num_samples` (default 50) to estimate the posterior distribution of the target variable.
4.  **Decision:**
    *   The engine calculates the mean risk probability.
    *   If Risk > Limit (0.50), it returns `DENY`.
    *   Otherwise, it returns `ALLOW`.
5.  **Output:** A structured `GovernanceResult` is returned to the `supervisor_node`.

### 4.2. Offline Policy Induction Flow

This flow is executed periodically (e.g., CI/CD or Cron) to "harden" the System 1 rules.

1.  **Artifact Loading:** The script loads the latest `prod_scm_v1.pkl`.
2.  **Scenario Generation:** The script generates a grid of scenarios (e.g., varying Tenure, Amount, Location).
3.  **Simulation Loop:** For each scenario, it asks: "If we BLOCK this user, does Churn Risk exceed 45%?"
4.  **Threshold Identification:** The script identifies the exact boundary (e.g., Tenure >= 7.5 years) where the risk limit is breached.
5.  **Policy Synthesis:**
    *   A Rego policy template is populated with the discovered threshold.
    *   Metadata (Timestamp, Source) is injected.
6.  **Persistence:** The file `policies/generated_causal_rules.rego` is written to disk.
7.  **Deployment:** The next `deployment/deploy_all.py` run bundles this new rule into the OPA secret, effectively migrating the check from "Slow System 2" to "Fast System 1".

## 5. Class Design & Interactions

### `ProductionSCM` (Singleton)
*   **Attributes:**
    *   `scm`: The loaded `dowhy.gcm.StructuralCausalModel`.
*   **Methods:**
    *   `__init__(model_path)`: Loads model or creates fallback.
    *   `simulate_intervention(context, intervention, target, samples)`: Core logic.

### `system_2_simulation_node` (Functional Node)
*   **Inputs:** `state: Dict[str, Any]`
*   **Logic:**
    *   Extracts `proposed_action`.
    *   Calls `scm_engine.simulate_intervention`.
    *   Compares result against `RISK_LIMIT`.
*   **Outputs:** `dict` (Update to `AgentState`).

## 6. Dependencies

*   **`dowhy`**: Provides the GCM implementation and causal reasoning algorithms.
*   **`networkx`**: Manages the graph structure.
*   **`pandas`**: Handles data frames for batch processing during simulation.
*   **`joblib`**: Handles efficient object serialization of the SCM.

## 7. Machine Learning Implementation Details (ML Engineers)

This section details the specific implementation of the Structural Causal Model (SCM) using `dowhy.gcm` and the mechanism choices for those extending or retraining the model.

### 7.1. Structural Causal Model (SCM)

The core of the engine is a `dowhy.gcm.StructuralCausalModel` wrapping a `networkx.DiGraph`.

*   **Graph Structure:** Defined in `scripts/train_causal_model.py`. It is a Directed Acyclic Graph (DAG) representing the causal dependencies.
    *   *Nodes:* `Transaction_Amount`, `Location_Mismatch`, `Fraud_Risk`, `Customer_Friction`, `Tenure_Years`, `Churn_Probability`.
    *   *Edges:* e.g., `Fraud_Risk -> Customer_Friction`.

### 7.2. Causal Mechanisms

We utilize `dowhy.gcm`'s mechanism assignment to model the functional relationships between parents and children.

*   **Root Nodes:** Modeled as `gcm.ScipyDistribution` or `gcm.EmpiricalDistribution` based on the input data.
*   **Intermediate/Leaf Nodes:**
    *   **Auto-Assignment:** We primarily use `gcm.auto.assign_causal_mechanisms(scm, data)` which attempts to select the best fit (Linear, Non-Linear) automatically.
    *   **Explicit Overrides:** For critical nodes like `Customer_Friction` and `Churn_Probability`, we explicitly utilize **Non-Linear Additive Noise Models (ANM)** wrapping Gradient Boosting Regressors:
        ```python
        scm.set_causal_mechanism('Churn_Probability',
            gcm.AdditiveNoiseModel(gcm.ml.create_hist_gradient_boost_regressor()))
        ```
    *   *Rationale:* Financial risk functions often exhibit sharp thresholds and non-linear interactions (e.g., the "Insult Effect" where tenure amplifies churn sensitivity under high friction), which linear models fail to capture.

### 7.3. The Do-Operator (Interventions)

The `simulate_intervention` method in `src/causal/engine.py` implements Pearl's Do-Operator ($P(Y | do(X))$).

1.  **Mutilation:** We modify the graph by removing incoming edges to the intervened node (`X`).
2.  **Forcing Values:** The value of `X` is forced to the intervention value (e.g., `0.9` for BLOCK) using a lambda function:
    ```python
    intervention_func[k] = lambda x, val=v: x * 0 + val
    ```
    This ensures the variable takes the fixed value regardless of its parents.
3.  **Sampling:** We use `gcm.interventional_samples`.
    *   *Conditioning:* The simulation is conditioned on the `filtered_context` (the specific user's current state).
    *   *Counterfactuals:* By conditioning on observed data *and* applying an intervention, we are effectively performing a counterfactual query: "Given what we know about *this specific user*, what *would have happened* if we blocked them?"

### 7.4. Training Strategy

*   **Synthetic Data:** Due to the lack of labeled "counterfactual" production data (we can't observe both "blocked" and "not blocked" for the same transaction), we bootstrap the model using synthetic data generation logic in `scripts/train_causal_model.py`.
*   **Generation Logic:** This logic encodes domain expert assumptions (e.g., "High Amount + Location Mismatch -> High Fraud Risk") into a generative process to create a training dataframe.
*   **Future State:** As production data accumulates, this synthetic step will be replaced by fitting the SCM directly on observational logs, potentially using Causal Discovery techniques (e.g., PC Algorithm) to refine the graph structure.

## 8. Connection to STAMP/STPA

This subsystem is the computational realization of the **Systems-Theoretic Accident Model and Processes (STAMP)** safety framework used throughout the Sovereign Stack.

### 8.1. Process Models & Flaws
*   **Concept:** In STPA, accidents often occur because the Controller's (AI Agent) internal "Process Model" (beliefs about the system) diverges from reality.
*   **Implementation:**
    *   The AI Agent acts on *implicit* beliefs (learned patterns).
    *   The `ProductionSCM` acts as the explicit, high-fidelity **Reference Process Model**.
    *   When System 2 is triggered, we validate the Agent's intent against this Reference Model. If the Agent proposes an action that the SCM predicts is dangerous, we have computationally identified a **Process Model Flaw** (the agent misunderstood the risk).

### 8.2. Unsafe Control Actions (UCAs)
*   **Concept:** A UCA is a control action that, in a specific context, leads to a System Hazard.
*   **Implementation:**
    *   The `simulate_intervention` method functions as a dynamic **UCA Detector**.
    *   It formally evaluates the conditional: *If Action $A$ is taken in Context $C$, does $P(Hazard) > Threshold$?*
    *   If the result is `DENY`, the system has successfully intercepted a UCA before execution.

### 8.3. Safety Constraints (Policy Induction)
*   **Concept:** STPA prescribes "Safety Constraints" to prevent UCAs.
*   **Implementation:**
    *   The Offline Policy Induction pipeline (`scripts/causal_policy_induction.py`) automates the derivation of these constraints.
    *   By searching the state space for hazard boundaries (e.g., "Blocking becomes unsafe when Tenure > 7.5y"), it converts abstract safety boundaries into concrete **OPA Rego rules**.
    *   This closes the safety loop: Hazards discovered in System 2 (Causal) are compiled into Constraints for System 1 (Rules).
