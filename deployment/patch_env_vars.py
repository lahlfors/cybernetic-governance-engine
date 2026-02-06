import argparse
import json
import os
import sys
from google.auth import default
from google.auth.transport.requests import AuthorizedSession

def patch_reasoning_engine(project_id, region, engine_id, env_vars):
    credentials, _ = default()
    authed_session = AuthorizedSession(credentials)
    
    # Engine ID might be full resource name or just ID. Handle both.
    # Resource name: projects/{p}/locations/{l}/reasoningEngines/{id}
    if "/reasoningEngines/" in engine_id:
        resource_name = engine_id
    else:
        resource_name = f"projects/{project_id}/locations/{region}/reasoningEngines/{engine_id}"
        
    url = f"https://{region}-aiplatform.googleapis.com/v1beta1/{resource_name}?updateMask=spec.deploymentSpec.env"
    
    # Construct EnvVar list
    env_list = [{"name": k, "value": v} for k, v in env_vars.items()]
    
    body = {
        "spec": {
            "deploymentSpec": {
                "env": env_list
            }
        }
    }
    
    print(f"Patching Reasoning Engine {resource_name}...")
    response = authed_session.patch(url, json=body)
    
    if response.status_code != 200:
        print(f"Error patching engine: {response.status_code} {response.text}")
        sys.exit(1)
        
    print("Successfully updated environment variables.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--engine-id", required=True)
    parser.add_argument("--env-vars", required=True, help="JSON string of env vars")
    
    args = parser.parse_args()
    env_vars = json.loads(args.env_vars)
    patch_reasoning_engine(args.project_id, args.region, args.engine_id, env_vars)
