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

"""
Graph Definition: MACAW Architecture (Sequential Blocking Execution)
Planner -> Evaluator -> Executor -> Explainer
"""

from langgraph.graph import END, StateGraph

from .checkpointer import get_checkpointer
from .nodes.adapters import (
    data_analyst_node,
    execution_analyst_node,
    governed_trader_node,
)
from .nodes.evaluator_node import evaluator_node
from .nodes.explainer_node import explainer_node
from .nodes.supervisor_node import supervisor_node
from .state import AgentState


def create_graph(redis_url=None):
    workflow = StateGraph(AgentState)

    # 1. Add Nodes
    workflow.add_node("supervisor", supervisor_node)

    # Specialized Agents
    workflow.add_node("data_analyst", data_analyst_node)

    # MACAW Pipeline Nodes
    workflow.add_node("execution_analyst", execution_analyst_node) # Planner (System 4)
    workflow.add_node("evaluator", evaluator_node)                 # Control (System 3)
    workflow.add_node("governed_trader", governed_trader_node)     # Executor (System 1)
    workflow.add_node("explainer", explainer_node)                 # Monitoring (System 3)

    workflow.add_node("human_review", lambda x: x) # Placeholder

    # 2. Entry Point
    workflow.set_entry_point("supervisor")

    # 3. Supervisor Routing (Intent -> Role)
    workflow.add_conditional_edges("supervisor", lambda x: x["next_step"], {
        "data_analyst": "data_analyst",
        "risk_analyst": "execution_analyst", # Fallback
        "execution_analyst": "execution_analyst",
        "evaluator": "evaluator", # Direct route if re-entry
        "governed_trader": "execution_analyst", # Enforce: Must start at Planner
        "explainer": "explainer",
        "human_review": "human_review",
        "FINISH": END
    })

    # 4. MACAW Sequential Flow

    # Planner -> Evaluator (Simulation)
    workflow.add_edge("execution_analyst", "evaluator")

    # Evaluator -> Conditional (Executor OR Back to Planner)
    workflow.add_conditional_edges("evaluator", lambda x: x["next_step"], {
        "governed_trader": "governed_trader",    # Approved
        "execution_analyst": "execution_analyst" # Rejected (Re-plan)
    })

    # Executor -> Explainer (Faithfulness)
    workflow.add_edge("governed_trader", "explainer")

    # Explainer -> Finish/Supervisor
    workflow.add_edge("explainer", "supervisor")

    # 5. Other Loops
    workflow.add_edge("data_analyst", "supervisor")
    workflow.add_edge("human_review", "supervisor")

    return workflow.compile(
        checkpointer=get_checkpointer(redis_url),
        interrupt_before=["human_review"]
    )
