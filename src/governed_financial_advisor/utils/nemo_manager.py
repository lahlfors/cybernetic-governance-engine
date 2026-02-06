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
Factory for creating NeMo Guardrails manager with custom Gemini support.
Supports Remote Guardrails via HTTP.
"""
import datetime
import logging
import os
from typing import Any, Optional

import nest_asyncio
import yaml
import httpx
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

# Conditional Import of NeMo
try:
    from nemoguardrails import LLMRails, RailsConfig
    from nemoguardrails.context import streaming_handler_var
    from nemoguardrails.llm.providers import register_llm_provider
    from langchain_core.language_models.llms import LLM
    HAS_NEMO = True
except ImportError:
    HAS_NEMO = False
    LLMRails = Any # Type alias for static analysis check skipping
    RailsConfig = Any
    LLM = Any


# Configure Logging
logger = logging.getLogger("NeMoManager")
tracer = trace.get_tracer(__name__)

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
        contents = [Content(role="user", parts=[Part.from_text(system_prompt)])]

        cache = CachedContent.create(
            model_name=model_name,
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

if HAS_NEMO:
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
else:
    # Dummy classes if NeMo is missing
    GeminiLLM = Any


def create_nemo_manager(config_path: str = "config/rails") -> Optional[Any]:
    """
    Creates and initializes a NeMo Guardrails manager.
    Returns None if using Remote Service or if NeMo is not installed.
    """
    # 1. Check for Remote Configuration
    if os.environ.get("NEMO_SERVICE_URL"):
        logger.info(f"🌐 configured to use Remote NeMo Service at {os.environ.get('NEMO_SERVICE_URL')}")
        return None

    if not HAS_NEMO:
        raise RuntimeError("nemoguardrails not installed. Cannot initialize local Rails.")

    global CACHED_CONTENT_NAME

    # Fix for nested event loops
    try:
        nest_asyncio.apply()
    except Exception:
        pass

    # Register custom Gemini provider
    register_llm_provider("gemini", GeminiLLM)

    # Resolve config path
    if not os.path.exists(config_path):
        cwd_path = os.path.join(os.getcwd(), config_path)
        if os.path.exists(cwd_path):
            config_path = cwd_path
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            possible_path = os.path.join(base_dir, "rails_config")
            if os.path.exists(possible_path):
                config_path = possible_path

    if not os.path.exists(config_path):
        # Fail softly if config missing?
        logger.warning(f"NeMo Guardrails config not found at: {config_path}")
        return None

    # Initialize Cache if using Vertex AI
    if os.environ.get("ENABLE_GOVERNANCE_CACHE", "true").lower() == "true":
        model_name = os.environ.get("GUARDRAILS_MODEL_NAME", "gemini-2.0-flash")
        CACHED_CONTENT_NAME = _get_or_create_cache(config_path, model_name)

    config = RailsConfig.from_path(config_path)
    rails = LLMRails(config)

    # Explicitly register actions to avoid import resolution issues
    # This is more robust than relying on NeMo's import mechanism
    try:
        from governed_financial_advisor.governance.nemo_actions import (
            check_approval_token,
            check_data_latency,
            check_drawdown_limit,
            check_slippage_risk,
            check_atomic_execution,
        )
        rails.register_action(check_approval_token, "check_approval_token")
        rails.register_action(check_data_latency, "check_data_latency")
        rails.register_action(check_drawdown_limit, "check_drawdown_limit")
        rails.register_action(check_slippage_risk, "check_slippage_risk")
        rails.register_action(check_atomic_execution, "check_atomic_execution")
        logger.info("✅ NeMo actions registered successfully")
    except ImportError as e:
        logger.warning(f"⚠️ Could not import NeMo actions: {e}")

    return rails

def load_rails() -> Optional[Any]:
    """Wrapper to maintain consistency with new design."""
    return create_nemo_manager()

async def validate_with_nemo(user_input: str, rails: Optional[Any] = None) -> tuple[bool, str]:
    """
    Validates user input using NeMo Guardrails (Local or Remote).
    Returns (is_safe: bool, response: str).
    Raises Exception if validation fails to execute (Fail Closed).
    """
    remote_url = os.environ.get("NEMO_SERVICE_URL")
    
    # Start OTel span
    with tracer.start_as_current_span("guardrails.validate_input") as span:
        span.set_attribute("guardrails.input_length", len(user_input))

        # --- REMOTE MODE ---
        if remote_url:
            span.set_attribute("guardrails.mode", "remote")
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"{remote_url}/v1/guardrails/check",
                        json={"input": user_input},
                        timeout=10.0
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    
                    response_content = data.get("response", "")
                    
                    # Heuristic Check
                    is_safe = True
                    if any(phrase in response_content for phrase in ["I cannot answer", "policy", "I am programmed", "I am sorry"]):
                        is_safe = False
                    
                    span.set_attribute("guardrails.outcome", "ALLOWED" if is_safe else "BLOCKED")
                    return is_safe, response_content
            except Exception as e:
                logger.error(f"Remote Guardrail Check Failed: {e}")
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR))
                # Production: Fail Closed. Governance is mandatory.
                raise RuntimeError(f"Governance Check Failed (Remote): {e}")

        # --- LOCAL MODE ---
        if not rails:
            # If no rails and no remote, this is a misconfiguration in Production.
            error_msg = "Guardrails not configured (No Remote URL and No Local Rails)"
            logger.error(error_msg)
            span.set_status(Status(StatusCode.ERROR, error_msg))
            raise RuntimeError(error_msg)

        span.set_attribute("guardrails.mode", "local")
        if not HAS_NEMO:
             raise RuntimeError("NeMo Guardrails not installed but Local Mode requested.")

        # Initialize callback
        from src.governed_financial_advisor.infrastructure.telemetry.nemo_exporter import NeMoOTelCallback
        handler = NeMoOTelCallback()
        token = streaming_handler_var.set(handler)

        try:
            res = await rails.generate_async(
                messages=[{"role": "user", "content": user_input}],
                streaming_handler=handler
            )

            is_safe = True
            response_content = ""

            if res and isinstance(res, dict) and "content" in res:
                content = res["content"]
                if any(phrase in content for phrase in ["I cannot answer", "policy", "I am programmed", "I am sorry"]):
                    is_safe = False
                    response_content = content
                else:
                    response_content = content
            elif isinstance(res, str):
                 if any(phrase in res for phrase in ["I cannot answer", "policy", "I am programmed", "I am sorry"]):
                    is_safe = False
                    response_content = res
                 else:
                    response_content = res

            span.set_attribute("guardrails.outcome", "ALLOWED" if is_safe else "BLOCKED")
            return is_safe, response_content

        except Exception as e:
            logger.error(f"NeMo Validation Error: {e}")
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR))
            # Production: Fail Closed.
            raise RuntimeError(f"Governance Check Failed (Local): {e}")
        finally:
            streaming_handler_var.reset(token)
