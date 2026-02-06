
import os
import argparse
import time
from google.api_core.client_options import ClientOptions
from google.cloud import discoveryengine_v1alpha as discoveryengine

def get_client_options(location):
    api_endpoint = f"{location}-discoveryengine.googleapis.com" if location != "global" else "discoveryengine.googleapis.com"
    return ClientOptions(api_endpoint=api_endpoint)

def list_engines(project_id, location):
    client_options = get_client_options(location)
    client = discoveryengine.EngineServiceClient(client_options=client_options)
    parent = f"projects/{project_id}/locations/{location}/collections/default_collection"
    
    print(f"Listing engines in {parent}...")
    try:
        request = discoveryengine.ListEnginesRequest(parent=parent)
        page_result = client.list_engines(request=request)
        engines = [e for e in page_result]
        return engines
    except Exception as e:
        print(f"Error listing engines: {e}")
        return []

def create_engine(project_id, location, display_name, engine_id):
    client_options = get_client_options(location)
    client = discoveryengine.EngineServiceClient(client_options=client_options)
    parent = f"projects/{project_id}/locations/{location}/collections/default_collection"
    
    engine = discoveryengine.Engine()
    engine.display_name = display_name
    engine.solution_type = discoveryengine.SolutionType.SOLUTION_TYPE_CHAT
    # engine.start_chat_feature_config... # Defaults might be okay
    
    print(f"Creating Engine {engine_id}...")
    operation = client.create_engine(
        parent=parent,
        engine=engine,
        engine_id=engine_id
    )
    response = operation.result()
    print(f"Engine created: {response.name}")
    return response

def register_agent(project_id, location, engine_id, reasoning_engine_id, agent_display_name):
    client_options = get_client_options(location)
    client = discoveryengine.AgentServiceClient(client_options=client_options)
    
    parent = f"projects/{project_id}/locations/{location}/collections/default_collection/engines/{engine_id}"
    
    # Check if agent already exists? (List agents)
    # But we want to Create a NEW one or specific one.
    
    agent = discoveryengine.Agent()
    agent.display_name = agent_display_name
    agent.description = "A Governed Financial Advisor agent that provides investment advice with risk checks."

    # IMPORTANT: The engine field must be the Full Resource Name of the Vertex AI Reasoning Engine
    # Format: projects/{project}/locations/{location}/reasoningEngines/{id}
    # reasoning_engine_id passed here is usually just the ID, so construct full path if needed,
    # OR if it is already full path, use it.

    if "projects/" in reasoning_engine_id:
        agent.engine = reasoning_engine_id
    else:
        agent.engine = f"projects/{project_id}/locations/{location}/reasoningEngines/{reasoning_engine_id}"
    
    print(f"Registering Agent '{agent_display_name}' to Engine '{engine_id}'...")
    print(f"Linking Reasoning Engine: {agent.engine}")
    
    try:
        # Create Agent
        request = discoveryengine.CreateAgentRequest(
            parent=parent,
            agent=agent,
            agent_id="financial-advisor-agent" # Explicit ID
        )
        response = client.create_agent(request=request)
        print(f"✅ Agent registered successfully: {response.name}")
        return response
    except Exception as e:
        print(f"❌ Error registering agent: {e}")
        # Try listing to see if it exists
        return None

def main():
    parser = argparse.ArgumentParser(description="Register Agent with Gemini Enterprise")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--location", default="us-central1") # Discovery Engine location
    parser.add_argument("--reasoning-engine-id", required=True)
    args = parser.parse_args()
    
    project_id = args.project_id
    location = args.location
    reasoning_engine_id = args.reasoning_engine_id
    
    # 1. Ensure we have an App (Engine)
    app_id = "financial-advisor-app"
    try:
        engines = list_engines(project_id, location)
        found_engine = next((e for e in engines if e.name.endswith(f"/engines/{app_id}")), None)

        if not found_engine:
            print(f"App '{app_id}' not found. Creating...")
            found_engine = create_engine(project_id, location, "Financial Advisor App", app_id)
        else:
            print(f"Found existing App: {found_engine.name}")

        # 2. Register Agent
        register_agent(project_id, location, app_id, reasoning_engine_id, "Financial Advisor")
        
    except ImportError:
         print("❌ google-cloud-discoveryengine not installed. Skipping registration.")

if __name__ == "__main__":
    main()
