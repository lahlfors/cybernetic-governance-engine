import os
import sys
from google.genai import Client, types

# Mock config
PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "laah-cybernetics")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
MODEL = "gemini-2.5-flash-lite" 

def perform_google_search(query: str) -> str:
    """Performs a Google Search using the Gemini model's native grounding capability."""
    return "Mock search result: AAPL looks good."

def transfer_to_agent(agent_name: str) -> None:
    """Transfers control to the specified agent."""
    print(f"Transferring to {agent_name}")

SYSTEM_INSTRUCTION = """
Agent Role: data_analyst
Tool Usage: Exclusively use the Google Search tool.
... (truncated for brevity, but simulating complexity) ...
IMMEDIATELY AFTER generating this report, you MUST call `transfer_to_agent("financial_coordinator")`.
"""

def main():
    print(f"Testing Model: {MODEL} with Project: {PROJECT}, Location: {LOCATION}")
    
    try:
        client = Client(vertexai=True, project=PROJECT, location=LOCATION)
        
        print("\n--- Test 2: Full Agent Simulation ---")
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents="Research AAPL",
                config=types.GenerateContentConfig(
                    tools=[perform_google_search, transfer_to_agent],
                    temperature=0.0,
                    system_instruction=SYSTEM_INSTRUCTION
                )
            )
            print("Success (Test 2)!")
            print(f"Text: {response.text}")
            print(f"Function Calls: {response.function_calls}")
        except Exception as e:
            print(f"Error (Test 2): {e}")

    except Exception as e:
        print(f"Fatal Error: {e}")

if __name__ == "__main__":
    main()
