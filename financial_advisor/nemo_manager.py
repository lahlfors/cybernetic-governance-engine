"""
Factory for creating NeMo Guardrails manager.
"""
import os
import nest_asyncio
from nemoguardrails import LLMRails, RailsConfig

def create_nemo_manager(config_path: str = "financial_advisor/rails_config") -> LLMRails:
    """
    Creates and initializes a NeMo Guardrails manager.

    Args:
        config_path: Path to the guardrails configuration directory.
                     Defaults to 'financial_advisor/rails_config'.

    Returns:
        An initialized LLMRails instance.
    """
    # Fix for nested event loops
    try:
        nest_asyncio.apply()
    except Exception:
        pass

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
