"""
Factory for creating NeMo Guardrails manager with custom Gemini support.
"""
import os
import nest_asyncio
from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.llm.providers import register_llm_provider
from langchain_core.language_models.llms import LLM
from typing import Any, List, Optional


class GeminiLLM(LLM):
    """Custom LangChain-compatible wrapper for Google Gemini using Vertex AI."""
    
    model: str = os.environ.get("GUARDRAILS_MODEL_NAME", "gemini-2.0-flash")
    
    @property
    def _llm_type(self) -> str:
        return "gemini"
    
    def _call(self, prompt: str, stop: Optional[List[str]] = None, **kwargs: Any) -> str:
        """Call the Gemini model via Vertex AI."""
        try:
            # Use Vertex AI integration (works with service account)
            from langchain_google_vertexai import ChatVertexAI
            
            llm = ChatVertexAI(
                model_name=self.model,
                project=os.environ.get("GOOGLE_CLOUD_PROJECT", "laah-cybernetics"),
                location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
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
    
    async def _acall(self, prompt: str, stop: Optional[List[str]] = None, **kwargs: Any) -> str:
        """Async call to the Gemini model via Vertex AI."""
        try:
            from langchain_google_vertexai import ChatVertexAI
            
            llm = ChatVertexAI(
                model_name=self.model,
                project=os.environ.get("GOOGLE_CLOUD_PROJECT", "laah-cybernetics"),
                location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
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
    try:
        # Check for 'self_check_input' or similar rails
        # We perform a generation call which triggers the input rails
        # If blocked, the response will be a refusal message.
        res = await rails.generate_async(messages=[{
            "role": "user",
            "content": user_input
        }])

        # Heuristic: Check if the response indicates a block
        # NeMo typically returns a predefined message if blocked by a rail
        if res and isinstance(res, dict) and "content" in res:
            content = res["content"]
            if "I cannot answer" in content or "policy" in content.lower():
                return False, content
            # If it's a pass-through or a normal response, we treat it as safe
            # Note: In a 'Governance Sandwich', we might just check input rails here
            # but NeMo usually runs generation.
            # A strict input check might use rails.generate(..., options={"rails": ["input"]})
            return True, content

        # If response object structure varies (e.g. string)
        if isinstance(res, str):
             if "I cannot answer" in res or "policy" in res.lower():
                return False, res
             return True, res

        return True, ""
    except Exception as e:
        print(f"NeMo Validation Error: {e}")
        # Fail safe (or fail closed depending on policy)
        # Here we allow the graph to proceed if NeMo crashes,
        # relying on the Graph's internal safety.
        return True, ""
