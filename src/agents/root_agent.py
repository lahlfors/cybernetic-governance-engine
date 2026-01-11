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

from google.adk.agents import LlmAgent
from src.tools.router import route_request
from src.utils.telemetry import configure_telemetry
from .prompt import get_financial_coordinator_instruction
import logging

logger = logging.getLogger("FinancialCoordinator")

# Initialize GCP observability (logging and tracing)
configure_telemetry()

from .data_analyst import data_analyst_agent

from .execution_analyst import execution_analyst_agent
from .governed_trader import governed_trading_agent
from .risk_analyst import risk_analyst_agent


MODEL = "gemini-2.5-pro"

financial_coordinator = LlmAgent(
    name="financial_coordinator",
    model=MODEL,
    description=(
        "guide users through a structured process to receive financial "
        "advice by orchestrating a series of expert subagents. help them "
        "analyze a market ticker, develop trading strategies, define "
        "execution plans, and evaluate the overall risk."
    ),
    instruction=get_financial_coordinator_instruction(),
    output_key="financial_coordinator_output",
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

