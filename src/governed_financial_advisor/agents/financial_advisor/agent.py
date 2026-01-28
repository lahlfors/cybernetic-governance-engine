# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Financial coordinator: provide reasonable investment strategies."""

import logging

from google.adk.agents import LlmAgent

from config.settings import MODEL_NAME
from src.tools.router import route_request
from src.utils.telemetry import configure_telemetry

from .callbacks import otel_interceptor_callback
from .prompt import get_financial_coordinator_instruction

logger = logging.getLogger("FinancialCoordinator")

# Initialize GCP observability (logging and tracing)
configure_telemetry()

# Import Factory Functions
from src.agents.data_analyst import create_data_analyst_agent
from src.agents.execution_analyst import create_execution_analyst_agent
from src.agents.governed_trader import create_governed_trader_agent
from src.agents.risk_analyst import create_risk_analyst_agent

# Instantiate Agents
data_analyst_agent = create_data_analyst_agent()
execution_analyst_agent = create_execution_analyst_agent()
governed_trading_agent = create_governed_trader_agent()
risk_analyst_agent = create_risk_analyst_agent()


financial_coordinator = LlmAgent(
    name="financial_coordinator",
    model=MODEL_NAME,
    description=(
        "guide users through a structured process to receive financial "
        "advice by orchestrating a series of expert subagents. help them "
        "analyze a market ticker, develop trading strategies, define "
        "execution plans, and evaluate the overall risk."
    ),
    instruction=get_financial_coordinator_instruction(),
    output_key="financial_coordinator_output",
    # Callback to inject OTel attributes (ISO 42001 Transparency)
    after_model_callback=otel_interceptor_callback,
    # Explicitly register sub-agents for hierarchy, but do not expose them as tools directly.
    sub_agents=[
        data_analyst_agent,
        governed_trading_agent,
        execution_analyst_agent,
        risk_analyst_agent,
    ],
    # Expose ONLY the deterministic router tool.
    tools=[
        route_request,
    ],
)

root_agent = financial_coordinator
agent = financial_coordinator
