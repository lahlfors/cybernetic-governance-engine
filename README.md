# Financial Advisor (Cybernetic Governance Edition)

**This repository implements the [Cybernetic Governance Framework](README_GOVERNANCE.md).**

## Overview

The Financial Advisor is a team of specialized AI agents that assists human financial advisors. It has been refactored to use a **Hierarchical Deterministic Markov Decision Process (HD-MDP)** for safety and control.

For details on the security architecture, including **Role-Based Access Control (RBAC)**, **Open Policy Agent (OPA)** integration, **Semantic Verification**, and **Consensus Engines**, please read **[README_GOVERNANCE.md](README_GOVERNANCE.md)**.

## Agent Team

1.  **Data Analyst Agent:** Market analysis via Google Search (accessed via Router).
2.  **Trading Analyst Agent (Governed):** Proposes strategies (Worker), subject to **Layer 3 Verification** (Verifier) and **Layer 4 Consensus**.
3.  **Execution Agent:** Creates detailed execution plans.
4.  **Risk Evaluation Agent:** Evaluates overall risk.

## Quick Start

### 1. Installation

```bash
# Clone this repository.
git clone https://github.com/google/adk-samples.git
cd adk-samples/python/agents/financial-advisor
# Install the package and dependencies.
uv sync
```

### 2. Governance Setup (Required)

You **must** have Open Policy Agent (OPA) running to execute trades or governed tools.

```bash
# Download OPA (Linux example)
curl -L -o opa https://openpolicyagent.org/downloads/v0.68.0/opa_linux_amd64_static
chmod 755 ./opa

# Run OPA in the background
./opa run -s -b . --addr :8181 &
```

### 3. Running the Agent

```bash
adk run financial_advisor
```

## Agent Architecture

This diagram shows the detailed architecture of the agents and tools used to implement this workflow.
<img src="financial-advisor.png" alt="Financial Advisor" width="800"/>

## Deployment

See [README_GOVERNANCE.md](README_GOVERNANCE.md#6-deployment-cloud-run-sidecar) for Cloud Run Sidecar deployment instructions.
