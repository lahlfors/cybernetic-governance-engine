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
Vertex AI Reasoning Engine Adapter for the Governed Financial Advisor.
This file defines the class structure required by the Vertex AI Reasoning Engine SDK.
"""

from typing import Dict, Any, List, Optional
from src.governed_financial_advisor.graph.graph import create_graph
from src.governed_financial_advisor.utils.nemo_manager import create_nemo_manager, validate_with_nemo
import os
import logging
import asyncio
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

class FinancialAdvisorEngine:
    """
    Adapter class for deploying the Financial Advisor on Vertex AI Agent Engine.
    Implements Option 1: The 'Library Wrapper' Pattern, where NeMo Guardrails
    run in-process to validate inputs before they reach the Agent Graph.
    """

    def __init__(self, project: str = None, location: str = "us-central1"):
        """
        Initializes the Financial Advisor Engine.

        Args:
            project: Google Cloud Project ID.
            location: Google Cloud Location.
        """
        self.project = project or os.environ.get("GOOGLE_CLOUD_PROJECT")
        self.location = location or os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        self.app = None
        self.rails = None

    def set_up(self):
        """
        Setup method called by Reasoning Engine runtime during initialization.
        Used to pre-warm connections or load heavy resources.
        """
        logger.info("Running set_up for FinancialAdvisorEngine...")
        
        # Option 1 (Library Wrapper): Ensure we run LOCALLY.
        # We explicitly do NOT fetch NEMO_SERVICE_URL from Secret Manager.
        # If the environment has it set, we unset it to force local mode,
        # unless explicitly overridden by a "FORCE_REMOTE" flag (optional, but let's keep it simple).
        if os.environ.get("NEMO_SERVICE_URL"):
            logger.warning("NEMO_SERVICE_URL is set in environment. Clearing it to force Local Mode (Library Wrapper).")
            del os.environ["NEMO_SERVICE_URL"]

        # Initialize NeMo Guardrails (Local Mode)
        # Assuming 'config/rails' is bundled in the deployment package at root or relative.
        logger.info("Initializing NeMo Guardrails (Local Mode)...")
        self.rails = create_nemo_manager("config/rails")
        if not self.rails:
             logger.error("Failed to initialize NeMo Guardrails locally.")
             # We might want to raise an error here to fail deployment if rails are critical.
             # raise RuntimeError("NeMo Guardrails initialization failed")

        # Initialize the graph here to ensure it uses the server environment
        # Redis removed in favor of MemorySaver / Native Vertex AI Memory
        self.app = create_graph()
        logger.info(f"FinancialAdvisorEngine initialized (Project: {self.project})")

    def query(self, prompt: str, thread_id: str = None) -> Dict[str, Any]:
        """
        The main entry point for the Reasoning Engine.

        Args:
            prompt: The user's input message.
            thread_id: Optional session ID for conversation state.

        Returns:
            A dictionary containing the agent's response and execution details.
        """

        # 1. NeMo Security Check (Input Rail) - Option 1: Library Wrapper
        if self.rails:
            try:
                # Handle Async Loop for validate_with_nemo
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                # Use loop to run async validation
                # Note: create_nemo_manager applies nest_asyncio, so re-entrant loops should work.
                is_safe, msg = loop.run_until_complete(validate_with_nemo(prompt, self.rails))

                if not is_safe:
                    logger.warning(f"Governance Input Rail BLOCKED: {prompt[:50]}...")
                    return {
                        "response": msg,
                        "blocked": True,
                        "state_snapshot": {}
                    }
            except Exception as e:
                logger.error(f"Governance Check failed: {e}")
                # Fail Closed
                return {"response": f"System Error during Governance Check: {e}", "error": str(e)}

        # 2. Agent Execution
        config = {"configurable": {"thread_id": thread_id or "default_thread"}}

        # Invoke the LangGraph workflow
        inputs = {
            "messages": [HumanMessage(content=prompt)],
            "plan": [],
            "feedback": "",
            "execution_result": {},
            "evaluation_result": {}
        }

        try:
            # We use invoke (blocking) as Reasoning Engine expects a synchronous response return
            result = self.app.invoke(inputs, config=config)

            # Extract the final response.
            messages = result.get("messages", [])
            last_message = messages[-1].content if messages else "No response generated."

            return {
                "response": last_message,
                "state_snapshot": {
                    "plan": result.get("plan"),
                    "execution_result": str(result.get("execution_result")),
                    "evaluation_result": str(result.get("evaluation_result"))
                }
            }
        except Exception as e:
            logger.error(f"Error during query execution: {e}")
            return {
                "response": f"System Error: {str(e)}",
                "error": str(e)
            }
