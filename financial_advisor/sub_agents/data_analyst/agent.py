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

"""data_analyst_agent for finding information using google search"""

from google.adk import Agent
from google.adk.tools.google_search_agent_tool import GoogleSearchAgentTool, create_google_search_agent
from google.adk.tools import transfer_to_agent

from . import prompt

MODEL = "gemini-2.5-pro"

# Create a dedicated search agent and wrap it as a tool
# This isolates the Google Search Retrieval tool to prevent conflicts with other function tools.
search_agent = create_google_search_agent(model=MODEL)
google_search_tool = GoogleSearchAgentTool(agent=search_agent)

data_analyst_agent = Agent(
    model=MODEL,
    name="data_analyst_agent",
    instruction=prompt.DATA_ANALYST_PROMPT,
    output_key="market_data_analysis_output",
    tools=[google_search_tool, transfer_to_agent],
)

