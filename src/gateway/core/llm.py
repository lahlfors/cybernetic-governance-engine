import json
import logging
from openai import AsyncOpenAI
from config.settings import Config

logger = logging.getLogger(__name__)

class GatewayClient:
    def __init__(self):
        # NEW: Support for GKE Inference Gateway (Single Endpoint)
        if Config.VLLM_GATEWAY_URL:
            logger.info(f"🚀 Using GKE Inference Gateway: {Config.VLLM_GATEWAY_URL}")
            self.mode = "gateway"
            self.gateway_client = AsyncOpenAI(
                base_url=Config.VLLM_GATEWAY_URL,
                api_key="EMPTY"
            )
        else:
            # LEGACY: Local / Split-Brain Mode
            logger.info("🔧 Using Local Split-Brain Mode (Direct Connection)")
            self.mode = "local"
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
        """
        Determines the (client, model) tuple based on the task mode.
        """
        if mode in ["planner", "reasoning", "analysis", "verifier"]:
            target_model = Config.MODEL_REASONING
            # In gateway mode, we always use the single client.
            # In local mode, we route to the reasoning service.
            client = self.gateway_client if self.mode == "gateway" else self.reasoning_client
            return client, target_model

        # Default / Governance / Fast tasks
        target_model = Config.MODEL_FAST
        client = self.gateway_client if self.mode == "gateway" else self.governance_client
        return client, target_model

    async def generate(self, prompt: str, system_instruction: str = None, mode: str = "chat", **kwargs) -> str:
        client, model = self._get_route(mode)

        # Handle FSM / Guided Generation
        extra_body = {}
        if "guided_json" in kwargs:
            extra_body["guided_json"] = kwargs.pop("guided_json")
        elif "guided_regex" in kwargs:
            extra_body["guided_regex"] = kwargs.pop("guided_regex")

        # In Gateway mode, we might want to pass priority headers in the future.
        # For now, relying on the model name in the body is sufficient for GKE routing.

        if extra_body:
            kwargs["extra_body"] = extra_body

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_instruction or "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM Generation Failed (Mode={mode}, Gateway={self.mode == 'gateway'}): {e}")
            raise
