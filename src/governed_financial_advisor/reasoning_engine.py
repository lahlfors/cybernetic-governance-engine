
"""
Vertex AI Reasoning Engine Adapter for the Governed Financial Advisor.
This file defines the class structure required by the Vertex AI Reasoning Engine SDK.
"""

from typing import Dict, Any, List, Optional
from src.governed_financial_advisor.graph.graph import create_graph
import os
import logging
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

class FinancialAdvisorEngine:
    """
    Adapter class for deploying the Financial Advisor on Vertex AI Agent Engine.
    """

    def __init__(self, project: str = None, location: str = "us-central1", redis_url: str = None):
        """
        Initializes the Financial Advisor Engine.

        Args:
            project: Google Cloud Project ID.
            location: Google Cloud Location.
            redis_url: URL for Redis State Store. If None, uses ephemeral memory (not recommended for production).
        """
        self.project = project or os.environ.get("GOOGLE_CLOUD_PROJECT")
        self.location = location or os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        self.redis_url = redis_url or os.environ.get("REDIS_URL")

        # Initialize the LangGraph Application
        # We perform lazy initialization of the graph here to capture any runtime config
        self.app = create_graph(redis_url=self.redis_url)
        logger.info(f"FinancialAdvisorEngine initialized (Project: {self.project}, Redis: {self.redis_url})")

    def set_up(self):
        """
        Setup method called by Reasoning Engine runtime during initialization.
        Used to pre-warm connections or load heavy resources.
        """
        # In a real scenario, we might verify Redis connection or pre-load embeddings here.
        pass

    def query(self, prompt: str, thread_id: str = None) -> Dict[str, Any]:
        """
        The main entry point for the Reasoning Engine.

        Args:
            prompt: The user's input message.
            thread_id: Optional session ID for conversation state.

        Returns:
            A dictionary containing the agent's response and execution details.
        """
        config = {"configurable": {"thread_id": thread_id or "default_thread"}}

        # Invoke the LangGraph workflow
        # The graph expects a dictionary with "messages" key or similar depending on State definition
        # Looking at graph.py, it uses AgentState. We assume it takes `messages` key implicitly via adapters.
        # Let's verify input format. Graph uses AgentState.

        inputs = {
            "messages": [HumanMessage(content=prompt)],
            # Initialize other state fields if necessary
            "plan": [],
            "feedback": "",
            "execution_result": {},
            "evaluation_result": {}
        }

        try:
            # We use invoke (blocking) as Reasoning Engine expects a synchronous response return
            # (even if under the hood it supports async, the default SDK pattern is often sync for `query`).
            # If the runtime supports async query, we could use ainvoke.
            # For now, sticking to synchronous invoke to be safe with standard RE templates.
            result = self.app.invoke(inputs, config=config)

            # Extract the final response.
            # The result is the final state. We need to extract the last message content.
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
