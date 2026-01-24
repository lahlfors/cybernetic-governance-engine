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
