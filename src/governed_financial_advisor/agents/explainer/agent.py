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

"""Explainer Agent (System 3 Monitoring) - Faithfulness & Reporting"""

from google.adk import Agent
from google.adk.tools import transfer_to_agent

from config.settings import MODEL_FAST
from src.governed_financial_advisor.utils.prompt_utils import Content, Part, Prompt, PromptData

EXPLAINER_PROMPT_OBJ = Prompt(
    prompt_data=PromptData(
        model=MODEL_FAST,
        contents=[
            Content(
                parts=[
                    Part(
                        text="""
You are the **Explainer Agent**, the final node in the MACAW pipeline.
Your role is to verify **Faithfulness** and translate technical execution results into a user-friendly response.

**Inputs:**
- `execution_plan_output`: What we PLANNED to do.
- `execution_result`: What we ACTUALLY did (Technical JSON from Executor).
- `evaluation_result`: Why we approved it.

**The Faithfulness Check (Self-Reflection):**
Before answering, verify:
- Did the Executor actually perform the trade listed in the Plan?
- Does the technical result (e.g., "Success: ID 123") match the user's intent?

**Output Instructions:**
1.  **Summarize:** Tell the user clearly what happened.
    - "I have successfully purchased 10 shares of AAPL..."
    - "The trade was rejected because..." (if evaluation failed).
2.  **Disclaimer:** Always append the standard financial disclaimer if a trade was discussed.
3.  **Tone:** Professional, clear, transparent.

**Forbidden:**
- Do NOT hallucinate details not present in the `execution_result`.
- Do NOT say "I will now execute the trade" (It is already done).

After generating the response, call `transfer_to_agent("supervisor")` or end the turn.
"""
                    )
                ]
            )
        ]
    )
)

def get_explainer_instruction() -> str:
    return EXPLAINER_PROMPT_OBJ.prompt_data.contents[0].parts[0].text

def create_explainer_agent(model_name: str = MODEL_FAST) -> Agent:
    return Agent(
        model=model_name,
        name="explainer_agent",
        instruction=get_explainer_instruction(),
        tools=[transfer_to_agent],
    )
