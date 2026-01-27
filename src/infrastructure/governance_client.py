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
    def __init__(
        self,
        base_url: str = "http://vllm-service.governance-stack.svc.cluster.local:8000/v1",
        api_key: str = "EMPTY",
        model_name: str = os.getenv("VLLM_MODEL", "google/gemma-3-27b-it"),
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
        self.model_name = model_name
        self.timeout = timeout_seconds

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_instruction: str = "You are a strict governance engine."
    ) -> T:
        """
        Generates a structured response strictly adhering to the provided Pydantic schema.
        Uses vLLM's `guided_json` (FSM/Outlines) to physically prevent invalid token generation.

        Args:
            prompt: The user input or context for the assessment.
            schema: The Pydantic model class defining the required structure.
            system_instruction: System prompt.

        Returns:
            An instance of the provided Pydantic schema class.
        """
        # 1. Convert Pydantic model to JSON Schema
        json_schema = schema.model_json_schema()

        # 2. Construct the payload with `guided_json`
        # This tells vLLM to compile the schema into an FSM/Regex for logit masking.
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0,  # Deterministic for governance
            "guided_json": json_schema, # The "Governance Sandwich" magic
            "max_tokens": 4096
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        url = f"{self.base_url}/chat/completions"

        logger.info(f"Sending Governed Request to {url} with schema {schema.__name__}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()

                result_data = response.json()
                content = result_data["choices"][0]["message"]["content"]

                # 3. Parse and Validate
                # vLLM guarantees the structure, but we parse it back to the Pydantic model
                return schema.model_validate_json(content)

            except httpx.HTTPError as e:
                logger.error(f"Governance Engine Communication Error: {str(e)}")
                raise RuntimeError(f"Governance Node failed: {str(e)}")
            except Exception as e:
                logger.error(f"Governance Validation Error: {str(e)}")
                raise
