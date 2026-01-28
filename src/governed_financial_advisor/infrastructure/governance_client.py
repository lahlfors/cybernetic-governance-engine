"""
GovernanceClient: Implements the "In-Process Governance" pattern.
Routes structured generation requests to the vLLM "Governance Node" (Logit Processor)
to enforce strict schema compliance via FSM (Finite State Machine) injection.
"""

import json
import logging
import os
from typing import Type, TypeVar, Optional

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

class GovernanceClient:
    # Default to the "Goldilocks" model: 9B parameters, fits on L4
    DEFAULT_MODEL_ID = "google/gemma-2-9b-it"

    def __init__(
        self,
        base_url: str = "http://vllm-service.governance-stack.svc.cluster.local:8000/v1",
        api_key: str = "EMPTY",
        model_name: Optional[str] = None,
        timeout_seconds: float = 30.0
    ):
        """
        Initializes the GovernanceClient for In-Process Governance.

        Args:
            base_url: The internal cluster URL for the vLLM service.
            api_key: API key for vLLM (usually EMPTY for internal).
            model_name: Model name to request from vLLM.
            timeout_seconds: Request timeout.
        """
        self.base_url = base_url
        self.api_key = api_key
        # Prioritize init arg, then env var, then class constant
        self.model_name = model_name or os.getenv("VLLM_MODEL", self.DEFAULT_MODEL_ID)
        self.timeout = timeout_seconds

    def _prepare_request(self, prompt: str, schema: Type[T], system_instruction: str) -> dict:
        """Helper to prepare the request payload."""
        json_schema = schema.model_json_schema()
        return {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0,
            "guided_json": json_schema,
            "max_tokens": 8192 # Increased for complex risk reports
        }

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_instruction: str = "You are a strict governance engine."
    ) -> T:
        """
        Generates a structured response strictly adhering to the provided Pydantic schema (Async).
        """
        payload = self._prepare_request(prompt, schema, system_instruction)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        url = f"{self.base_url}/chat/completions"

        logger.info(f"Sending Governed Request (Async) to {url} with schema {schema.__name__}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                result_data = response.json()
                content = result_data["choices"][0]["message"]["content"]
                return schema.model_validate_json(content)
            except Exception as e:
                logger.error(f"Governance Validation Error: {str(e)}")
                raise

    def generate_structured_sync(
        self,
        prompt: str,
        schema: Type[T],
        system_instruction: str = "You are a strict governance engine."
    ) -> T:
        """
        Generates a structured response strictly adhering to the provided Pydantic schema (Sync).
        Use this when calling from synchronous tool functions to avoid event loop conflicts.
        """
        payload = self._prepare_request(prompt, schema, system_instruction)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        url = f"{self.base_url}/chat/completions"

        logger.info(f"Sending Governed Request (Sync) to {url} with schema {schema.__name__}")

        with httpx.Client(timeout=self.timeout) as client:
            try:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                result_data = response.json()
                content = result_data["choices"][0]["message"]["content"]
                return schema.model_validate_json(content)
            except Exception as e:
                logger.error(f"Governance Validation Error: {str(e)}")
                raise
