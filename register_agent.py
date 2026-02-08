
import os
import argparse
import time
from google.api_core.client_options import ClientOptions
from google.cloud import discoveryengine_v1beta as discoveryengine

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

def create_data_store(project_id, location, data_store_id, display_name):
    client_options = get_client_options(location)
    client = discoveryengine.DataStoreServiceClient(client_options=client_options)
    parent = f"projects/{project_id}/locations/{location}/collections/default_collection"

    # Check existence
    try:
        request = discoveryengine.GetDataStoreRequest(
            name=f"{parent}/dataStores/{data_store_id}"
        )
        return client.get_data_store(request=request)
    except Exception:
        pass # Create new

    data_store = discoveryengine.DataStore()
    data_store.display_name = display_name
    data_store.industry_vertical = discoveryengine.IndustryVertical.GENERIC
    data_store.solution_types = [discoveryengine.SolutionType.SOLUTION_TYPE_CHAT]
    data_store.content_config = discoveryengine.DataStore.ContentConfig.NO_CONTENT # Placeholder

    print(f"Creating Data Store {data_store_id}...")
    operation = client.create_data_store(
        parent=parent,
        data_store=data_store,
        data_store_id=data_store_id
    )
    response = operation.result()
    print(f"Data Store created: {response.name}")
    return response

def register_agent(project_id, location, engine_id, reasoning_engine_id, agent_display_name):
    print(f"\n--- ⚠️ Automatic Registration Not Supported in this SDK Version ---")
    print(f"Please register the agent manually in the Google Cloud Console:")
    print(f"1. Go to: https://console.cloud.google.com/gen-app-builder/engines?project={project_id}")
    print(f"2. Select the App: '{engine_id}'")
    print(f"3. Go to 'Agent' section and click 'Register Agent'")
    print(f"4. Select 'Vertex AI Reasoning Engine' as the source.")
    print(f"5. Enter the Reasoning Engine ID: {reasoning_engine_id}")
    print(f"6. Click 'Register'")
    print(f"------------------------------------------------------------------\n")
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
            print(f"App '{app_id}' not found.")

            # 1.1 Create Data Store first (Required for App creation)
            ds_id = "financial-knowledge-base"
            data_store = create_data_store(project_id, location, ds_id, "Financial Knowledge Base")

            # 1.2 Create App with Data Store linked
            print(f"Creating App '{app_id}'...")

            client_options = get_client_options(location)
            client = discoveryengine.EngineServiceClient(client_options=client_options)
            parent = f"projects/{project_id}/locations/{location}/collections/default_collection"

            engine = discoveryengine.Engine()
            engine.display_name = "Financial Advisor App"
            engine.solution_type = discoveryengine.SolutionType.SOLUTION_TYPE_CHAT
            engine.data_store_ids = [ds_id] # Link Data Store

            # Configure Chat Engine (Language matches Data Store content usually, default en)
            engine.chat_engine_config = discoveryengine.Engine.ChatEngineConfig(
                agent_creation_config=discoveryengine.Engine.ChatEngineConfig.AgentCreationConfig(
                    default_language_code="en",
                    time_zone="America/Los_Angeles"
                )
            )

            engine.common_config = discoveryengine.Engine.CommonConfig(
                company_name="Cybernetic Governance"
            )

            operation = client.create_engine(
                parent=parent,
                engine=engine,
                engine_id=app_id
            )
            found_engine = operation.result()
            print(f"App created: {found_engine.name}")
        else:
            print(f"Found existing App: {found_engine.name}")

        # 2. Register Agent
        register_agent(project_id, location, app_id, reasoning_engine_id, "Financial Advisor")

    except ImportError:
         print("❌ google-cloud-discoveryengine not installed. Skipping registration.")

if __name__ == "__main__":
    main()
