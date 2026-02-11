import json
import logging
from openai import AsyncOpenAI
from config.settings import Config

logger = logging.getLogger(__name__)

class GatewayClient:
    def __init__(self):
        # Node A: The Brain
        self.reasoning_client = AsyncOpenAI(
            base_url=Config.VLLM_REASONING_API_BASE,
            api_key="EMPTY"
        )
        # Node B: The Police
        self.governance_client = AsyncOpenAI(
            base_url=Config.VLLM_FAST_API_BASE,
            api_key="EMPTY"
        )

    def _get_route(self, mode: str):
        """Routes complex tasks to Brain, fast tasks to Police."""
        if mode in ["planner", "reasoning", "analysis", "verifier"]:
            return self.reasoning_client, Config.MODEL_REASONING
        return self.governance_client, Config.MODEL_FAST

    async def generate(self, prompt: str, system_instruction: str = None, mode: str = "chat", **kwargs) -> str:
        client, model = self._get_route(mode)

        # Handle FSM / Guided Generation
        extra_body = {}
        if "guided_json" in kwargs:
            extra_body["guided_json"] = kwargs.pop("guided_json")
        elif "guided_regex" in kwargs:
            extra_body["guided_regex"] = kwargs.pop("guided_regex")

        if extra_body:
            kwargs["extra_body"] = extra_body

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_instruction or "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            **kwargs
        )
        return response.choices[0].message.content
