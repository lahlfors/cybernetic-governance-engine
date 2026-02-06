
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

    def __init__(self, project: str = None, location: str = "us-central1", gateway_url: str = None):
        """
        Initializes the Financial Advisor Engine.

        Args:
            project: Google Cloud Project ID.
            location: Google Cloud Location.
            gateway_url: URL of the Gateway Service.
        """
        self.project = project or os.environ.get("GOOGLE_CLOUD_PROJECT")
        self.location = location or os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        self.gateway_url = gateway_url
        self.app = None

    def set_up(self):
        """
        Setup method called by Reasoning Engine runtime during initialization.
        Used to pre-warm connections or load heavy resources.
        """
        logger.info("Running set_up for FinancialAdvisorEngine...")

        if self.gateway_url:
            os.environ["GATEWAY_HOST"] = self.gateway_url
            logger.info(f"Configured GATEWAY_HOST: {self.gateway_url}")
        
        # PROD: Fetch NeMo URL from Secret Manager if not in Env
        if not os.environ.get("NEMO_SERVICE_URL"):
            try:
                from google.cloud import secretmanager
                client = secretmanager.SecretManagerServiceClient()
                name = f"projects/{self.project}/secrets/nemo-service-url/versions/latest"
                response = client.access_secret_version(request={"name": name})
                nemo_url = response.payload.data.decode("UTF-8").strip()
                os.environ["NEMO_SERVICE_URL"] = nemo_url
                logger.info(f"Loaded NEMO_SERVICE_URL from Secret Manager: {nemo_url}")
            except Exception as e:
                logger.warning(f"Failed to load NEMO_SERVICE_URL from Secret Manager: {e}")

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
        config = {"configurable": {"thread_id": thread_id or "default_thread"}}

        # Invoke the LangGraph workflow
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
