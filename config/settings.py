import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    # Default to a fast model for the Supervisor
    DEFAULT_MODEL = os.getenv("MODEL_NAME", "gemini-2.5-flash")

    @staticmethod
    def get_llm_config(profile="default"):
        return {
            "model": Config.DEFAULT_MODEL,
            "temperature": 0.0,
            "google_api_key": Config.GOOGLE_API_KEY
        }
