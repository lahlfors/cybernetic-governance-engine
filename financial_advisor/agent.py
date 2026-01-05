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

from . import prompt
from .sub_agents.data_analyst import data_analyst_agent
from .sub_agents.execution_analyst import execution_analyst_agent
from .sub_agents.governed_trader.agent import governed_trading_agent
from .sub_agents.risk_analyst import risk_analyst_agent

MODEL = "gemini-2.5-pro"


_financial_coordinator = LlmAgent(
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


class GovernedAgent:
    """
    Wraps the LlmAgent with NeMo Guardrails.
    """

    def __init__(self, agent):
        self.agent = agent
        try:
            self.rails = create_nemo_manager()
            self.rails_active = True
        except Exception as e:
            print(f"Warning: Failed to initialize NeMo Guardrails: {e}")
            self.rails_active = False

    def __call__(self, prompt: str):
        # TODO: Implement full rails generation loop
        # For now, acts as a pass-through to ensure the agent still works
        # while rails are being configured.
        return self.agent(prompt)

    def __getattr__(self, name):
        """Proxy attribute access to the underlying agent."""
        return getattr(self.agent, name)


financial_coordinator = GovernedAgent(_financial_coordinator)

root_agent = financial_coordinator
