
import os
import argparse
import vertexai
from vertexai.preview import reasoning_engines

def verify_agent(project_id, location, resource_name=None):
    vertexai.init(project=project_id, location=location)

    if not resource_name:
        print("Searching for Reasoning Engine with display name 'financial-advisor-engine'...")
        # List all engines and find the one with display_name 'financial-advisor-engine'
        # simpler way: use the list method if available, or just rely on the user providing it if fails.
        # ReasoningEngine.list() is not always straightforward in preview, but let's try.
        try:
             engines = reasoning_engines.ReasoningEngine.list()
             target_engine = None
             for engine in engines:
                 if engine.display_name == "financial-advisor-engine":
                     target_engine = engine
                     break
             if target_engine:
                 resource_name = target_engine.resource_name
                 print(f"Found engine: {resource_name}")
             else:
                 print("Could not find engine with display name 'financial-advisor-engine'.")
                 return
        except Exception as e:
            print(f"Error listing engines: {e}")
            return

    print(f"Connecting to Reasoning Engine: {resource_name}")
    remote_agent = reasoning_engines.ReasoningEngine(resource_name)
    try:
        schemas = remote_agent.operation_schemas()
        print(f"Operation Schemas List: {schemas}")
    except Exception as e:
        print(f"Error getting operation schemas: {e}")

    print("Querying Agent...")
    try:
        response = remote_agent.query(prompt="Analyze GOOG stock.")
        print("Response received:")
        print(response)
    except Exception as e:
        print(f"Query failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", default=os.environ.get("GOOGLE_CLOUD_PROJECT", "laah-cybernetics"))
    parser.add_argument("--location", default="us-central1")
    parser.add_argument("--resource-name", help="Full resource name of the reasoning engine")
    args = parser.parse_args()

    verify_agent(args.project_id, args.location, args.resource_name)
