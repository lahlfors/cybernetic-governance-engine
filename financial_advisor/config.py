import os
from langchain_google_genai import ChatGoogleGenerativeAI

class Config:
    """Centralized Configuration"""
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")

    @classmethod
    def get_llm_config(cls, profile: str = "default"):
        return {
            "model": "gemini-2.5-flash",
            "temperature": 0.0,
            "google_api_key": cls.GOOGLE_API_KEY
        }
