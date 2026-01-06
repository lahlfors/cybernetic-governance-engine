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
# from google.adk.tools.agent_tool import AgentTool # Removed to enforce HD-MDP
from .tools.router import route_request
from .nemo_manager import create_nemo_manager
from .telemetry import configure_telemetry

# Initialize GCP observability (logging and tracing)
configure_telemetry()

from . import prompt
from .sub_agents.data_analyst import data_analyst_agent
from .sub_agents.execution_analyst import execution_analyst_agent
from .sub_agents.governed_trader.agent import governed_trading_agent
from .sub_agents.risk_analyst import risk_analyst_agent

MODEL = "gemini-2.5-pro"


class GovernedLlmAgent(LlmAgent):
    """
    Extension of LlmAgent that includes NeMo Guardrails.
    """
    _rails: object = None
    _rails_active: bool = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        try:
            self._rails = create_nemo_manager()
            self._rails_active = True
        except Exception as e:
            print(f"Warning: Failed to initialize NeMo Guardrails: {e}")
            self._rails_active = False

    def __call__(self, prompt: str):
        if self._rails_active:
            try:
                # Wrap input in NeMo Guardrails
                # Messages format: [{"role": "user", "content": prompt}]
                response = self._rails.generate(messages=[{"role": "user", "content": prompt}])

                # Check if response is a dict or string (depends on NeMo version/config)
                if isinstance(response, dict):
                    return response.get("content", str(response))
                return str(response)
            except Exception as e:
                print(f"Error in NeMo Guardrails: {e}. Falling back to standard execution.")
                return super().__call__(prompt)

        return super().__call__(prompt)


financial_coordinator = GovernedLlmAgent(
    name="financial_coordinator",
    model=MODEL,
    description=(
        "guide users through a structured process to receive financial "
        "advice by orchestrating a series of expert subagents. help them "
        "analyze a market ticker, develop trading strategies, define "
        "execution plans, and evaluate the overall risk."
    ),
    instruction=prompt.FINANCIAL_COORDINATOR_PROMPT,
    output_key="financial_coordinator_output",
    # Explicitly register sub-agents for hierarchy, but do not expose them as tools directly.
    sub_agents=[
        data_analyst_agent,
        governed_trading_agent,
        execution_analyst_agent,
        risk_analyst_agent,
    ],
    # Expose ONLY the deterministic router tool.
    tools=[route_request],
)

root_agent = financial_coordinator
