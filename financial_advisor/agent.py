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
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from .tools.router import route_request
from .telemetry import configure_telemetry
from .prompt import get_financial_coordinator_instruction
from financial_advisor.infrastructure.vertex_memory import get_memory_service
import logging

logger = logging.getLogger("FinancialCoordinator")

# --- NEW: Save Middleware ---
async def save_memory_callback(context, response):
    """
    Middleware: Automatically saves the turn to Vertex AI Memory Bank.
    Triggered after the agent generates a response.
    """
    session = context.session
    try:
        service = get_memory_service()
        if service:
            # Persist the session state/history to the Memory Bank
            await service.add_session_to_memory(session)
            print(f"💾 Memory Saved for Session: {session.id}")
        else:
            # Graceful degradation if memory service isn't active
            print("⚠️ Memory Service not active (skipping save).")
    except Exception as e:
        print(f"⚠️ Failed to save memory: {e}")

# ... existing code ...

# Initialize GCP observability (logging and tracing)
configure_telemetry()

from . import prompt
from .sub_agents.data_analyst import data_analyst_agent
from .sub_agents.execution_analyst import execution_analyst_agent
from .sub_agents.governed_trader.agent import governed_trading_agent
from .sub_agents.risk_analyst import risk_analyst_agent

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
        # --- NEW: Read Middleware ---
        # Automatically queries memory bank and injects relevant context
        PreloadMemoryTool()
    ],
    # --- NEW: Write Middleware ---
    after_model_callback=save_memory_callback,
)

root_agent = financial_coordinator
