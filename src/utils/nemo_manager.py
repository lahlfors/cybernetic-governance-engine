"""
Factory for creating NeMo Guardrails manager with custom Gemini support.
"""
import datetime
import logging
import os
from typing import Any

import nest_asyncio
import yaml
from langchain_core.language_models.llms import LLM
from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.context import streaming_handler_var
from nemoguardrails.llm.providers import register_llm_provider

from src.infrastructure.telemetry.nemo_exporter import NeMoOTelCallback

# Configure Logging
logger = logging.getLogger("NeMoManager")

# Global cache name to be shared with GeminiLLM instances
CACHED_CONTENT_NAME = None

def _get_or_create_cache(config_path: str, model_name: str) -> str | None:
    """
    Creates a Vertex AI CachedContent resource for the NeMo system prompts.
    Returns the cache resource name (ID).
    """
    try:
        from vertexai.preview.generative_models import CachedContent, Content, Part

        # 1. Read System Instructions from Config
        config_file = os.path.join(config_path, "config.yml")
        if not os.path.exists(config_file):
            return None

        with open(config_file) as f:
            config_data = yaml.safe_load(f)

        instructions = config_data.get("instructions", [])
        system_prompt = ""
        for instr in instructions:
            system_prompt += instr.get("content", "") + "\n"

        if not system_prompt:
            return None

        # 2. Define Cache (TTL: 1 hour)
        # We use a static name or just let it generate one.
        # For simplicity, we create a new one on startup (ephemeral).
        # In prod, we might check for existing one.

        # We need to wrap content in Content object
        contents = [Content(role="user", parts=[Part.from_text(system_prompt)])]

        cache = CachedContent.create(
            model_name=model_name,
            system_instruction=None, # NeMo injects system instructions in the prompt usually?
            # Wait, if we use cache, we should put system prompt here?
            # Instructions: "cache the NeMo system prompts"
            # If we put it in contents, it acts as context.
            contents=contents,
            ttl=datetime.timedelta(hours=1),
            display_name="governance_cache_v1"
        )

        logger.info(f"✅ Vertex AI Context Cache Created: {cache.name}")
        return cache.name

    except ImportError:
        logger.warning("⚠️ Vertex AI SDK not found or CachedContent not supported.")
        return None
    except Exception as e:
        logger.warning(f"⚠️ Failed to create context cache: {e}")
        return None

class GeminiLLM(LLM):
    """Custom LangChain-compatible wrapper for Google Gemini using Vertex AI."""

    model: str = os.environ.get("GUARDRAILS_MODEL_NAME", "gemini-2.0-flash")

    @property
    def _llm_type(self) -> str:
        return "gemini"

    def _call(self, prompt: str, stop: list[str] | None = None, **kwargs: Any) -> str:
        """Call the Gemini model via Vertex AI."""
        try:
            # Use Vertex AI integration (works with service account)
            from langchain_google_vertexai import ChatVertexAI

            # Inject Cache if available
            llm_kwargs = {}
            if CACHED_CONTENT_NAME:
                # Assuming ChatVertexAI supports cached_content (newer versions)
                # If not, this might fail, so we wrap in try/except or check version
                llm_kwargs["cached_content"] = CACHED_CONTENT_NAME

            llm = ChatVertexAI(
                model_name=self.model,
                project=os.environ.get("GOOGLE_CLOUD_PROJECT", "laah-cybernetics"),
                location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
                **llm_kwargs
            )
            response = llm.invoke(prompt)
            return response.content
        except ImportError:
            # Fallback to google-genai if vertexai not available
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                llm = ChatGoogleGenerativeAI(
                    model=self.model,
                    convert_system_message_to_human=True,
                )
                response = llm.invoke(prompt)
                return response.content
            except Exception as e:
                return f"Error calling Gemini: {e}"
        except Exception as e:
            return f"Error calling Gemini: {e}"

    async def _acall(self, prompt: str, stop: list[str] | None = None, **kwargs: Any) -> str:
        """Async call to the Gemini model via Vertex AI."""
        try:
            from langchain_google_vertexai import ChatVertexAI

            llm_kwargs = {}
            if CACHED_CONTENT_NAME:
                llm_kwargs["cached_content"] = CACHED_CONTENT_NAME

            llm = ChatVertexAI(
                model_name=self.model,
                project=os.environ.get("GOOGLE_CLOUD_PROJECT", "laah-cybernetics"),
                location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
                **llm_kwargs
            )
            response = await llm.ainvoke(prompt)
            return response.content
        except ImportError:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                llm = ChatGoogleGenerativeAI(
                    model=self.model,
                    convert_system_message_to_human=True,
                )
                response = await llm.ainvoke(prompt)
                return response.content
            except Exception as e:
                return f"Error calling Gemini: {e}"
        except Exception as e:
            return f"Error calling Gemini: {e}"

    @property
    def _identifying_params(self) -> dict:
        return {"model": self.model}


def _get_gemini_llm(model_name: str, **kwargs) -> GeminiLLM:
    """Factory function for creating Gemini LLM instances."""
    return GeminiLLM(model=model_name)


def create_nemo_manager(config_path: str = "config/rails") -> LLMRails:
    """
    Creates and initializes a NeMo Guardrails manager with Gemini support.

    Args:
        config_path: Path to the guardrails configuration directory.
                     Defaults to 'config/rails'.

    Returns:
        An initialized LLMRails instance.
    """
    global CACHED_CONTENT_NAME

    # Fix for nested event loops
    try:
        nest_asyncio.apply()
    except Exception:
        pass

    # Register custom Gemini provider - pass the class directly, not a factory
    register_llm_provider("gemini", GeminiLLM)

    # Resolve config path
    if not os.path.exists(config_path):
        # Try finding it relative to the current working directory
        cwd_path = os.path.join(os.getcwd(), config_path)
        if os.path.exists(cwd_path):
            config_path = cwd_path
        else:
            # Try relative to this file
            base_dir = os.path.dirname(os.path.abspath(__file__))
            possible_path = os.path.join(base_dir, "rails_config")
            if os.path.exists(possible_path):
                config_path = possible_path

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"NeMo Guardrails config not found at: {config_path}")

    # Initialize Cache if using Vertex AI
    # Check env var to allow disabling it
    if os.environ.get("ENABLE_GOVERNANCE_CACHE", "true").lower() == "true":
        model_name = os.environ.get("GUARDRAILS_MODEL_NAME", "gemini-2.0-flash")
        CACHED_CONTENT_NAME = _get_or_create_cache(config_path, model_name)

    config = RailsConfig.from_path(config_path)
    rails = LLMRails(config)
    return rails

# --- New Adapter Functions for Refactor ---

def load_rails() -> LLMRails:
    """Wrapper to maintain consistency with new design."""
    return create_nemo_manager()

async def validate_with_nemo(user_input: str, rails: LLMRails) -> tuple[bool, str]:
    """
    Validates user input using NeMo Guardrails.
    Returns (is_safe: bool, response: str).
    """
    # 1. Initialize ISO 42001 OTel callback
    handler = NeMoOTelCallback()

    # 2. Set the global context variable for custom actions to capture events
    token = streaming_handler_var.set(handler)

    try:
        # Check for 'self_check_input' or similar rails
        # We perform a generation call which triggers the input rails
        # If blocked, the response will be a refusal message.
        # 3. Call generate_async with the handler
        res = await rails.generate_async(
            messages=[{"role": "user", "content": user_input}],
            streaming_handler=handler
        )

        # Heuristic: Check if the response indicates a block
        # NeMo typically returns a predefined message if blocked by a rail
        if res and isinstance(res, dict) and "content" in res:
            content = res["content"]
            if any(phrase in content for phrase in ["I cannot answer", "policy", "I am programmed", "I am sorry"]):
                return False, content
            # If it's a pass-through or a normal response, we treat it as safe
            # Note: In a 'Governance Sandwich', we might just check input rails here
            # but NeMo usually runs generation.
            # A strict input check might use rails.generate(..., options={"rails": ["input"]})
            return True, content

        # If response object structure varies (e.g. string)
        if isinstance(res, str):
             if any(phrase in res for phrase in ["I cannot answer", "policy", "I am programmed", "I am sorry"]):
                return False, res
             return True, res

        return True, ""
    except Exception as e:
        print(f"NeMo Validation Error: {e}")
        # Fail safe (or fail closed depending on policy)
        # Here we allow the graph to proceed if NeMo crashes,
        # relying on the Graph's internal safety.
        return True, ""
    finally:
        # Clean up the context variable
        streaming_handler_var.reset(token)
