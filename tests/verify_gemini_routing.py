import os
import sys
import unittest

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))
sys.path.append(os.getcwd()) # Ensure root is in path

from gateway.core.llm import HybridClient
from config.settings import Config
from unittest.mock import patch

class TestGeminiRouting(unittest.TestCase):
    def test_gemini_routing_logic(self):
        # Initialize HybridClient with a dummy key to trigger Gemini Client creation
        with patch.object(Config, 'GOOGLE_API_KEY', 'dummy_key'):
            client = HybridClient()

        gemini_model = "gemini-1.5-pro"

        # This call is what we want to test.
        # Currently it should probably return the fast client (Llama) because logic isn't there.
        # After fix, it should return a Gemini client.

        # We need to see if we can detect what client it is.
        # Since we haven't imported google.genai in the main code yet, we can't check isinstance easily
        # without importing it here.

        try:
            from google import genai
            HAS_GENAI = True
        except ImportError:
            HAS_GENAI = False

        c, url, model = client._get_client_and_model(gemini_model, mode="reasoning")

        print(f"Client: {c}")
        print(f"URL: {url}")
        print(f"Model: {model}")

        # Check if it routed to Gemini
        # We expect this to fail or show incorrect routing before our changes
        # But we won't assert failure, we will use this to verify SUCCESS later.

        if HAS_GENAI and isinstance(c, genai.Client):
            print("SUCCESS: Routed to Gemini Client")
        else:
            print("FAILURE: Did not route to Gemini Client")

if __name__ == "__main__":
    unittest.main()
