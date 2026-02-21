import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

_langfuse_client = None

def get_langfuse_client():
    global _langfuse_client
    if _langfuse_client is None:
        public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
        secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
        host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
        
        if public_key and secret_key:
            try:
                from langfuse import Langfuse
                _langfuse_client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
            except Exception as e:
                logger.warning(f"Failed to initialize Langfuse client: {e}")
    return _langfuse_client

def get_managed_prompt(name: str, fallback_text: str, variables: Optional[Dict[str, Any]] = None) -> str:
    """
    Fetches a prompt from Langfuse Prompt Management with local client-side caching.
    Includes fallback logic to return the static text if the network or API fails.
    
    Args:
        name: The name of the Langfuse Prompt (e.g., 'agent/explainer')
        fallback_text: The hardcoded static text to use if fetching fails
        variables: Optional variables to inject via .compile(**variables)
    """
    try:
        client = get_langfuse_client()
        if client:
            # Enable 5-minute local cache to speed up repeated queries and reduce API calls
            prompt_obj = client.get_prompt(name, label="production", cache_ttl_seconds=300)
            if prompt_obj:
                print(f"✅ Successfully fetched '{name}' from Langfuse cache/API")
                if variables:
                    return prompt_obj.compile(**variables)
                return prompt_obj.compile()
    except Exception as e:
        logger.warning(f"⚠️ Failed to fetch or compile prompt '{name}' from Langfuse: {e}. Falling back to static prompt.")
    
    return fallback_text
