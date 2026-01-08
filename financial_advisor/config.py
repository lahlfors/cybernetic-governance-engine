import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL_NAME", "gemini-2.5-flash")
    REASONING_MODEL = os.getenv("REASONING_MODEL_NAME", "gemini-2.5-pro")
    NEMO_PATH = os.getenv("NEMO_CONFIG_PATH", "financial_advisor/rails_config")

    @staticmethod
    def get_llm_config(model_type="default"):
        return {
            "model": Config.REASONING_MODEL if model_type == "reasoning" else Config.DEFAULT_MODEL,
            # Lower temperature for synthesis consistency
            "temperature": 0.2
        }
