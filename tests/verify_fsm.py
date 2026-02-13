
import os
import requests
import json
import time

# Configuration
BACKEND_URL = os.environ.get("BACKEND_URL", "http://34.122.99.196")
# We want to target the FAST model path. 
# The Gateway routes 'fast' or 'classification' steps to vllm-inference.
# However, for direct verification, we can use the gateway's /agent/query if we can force the model 
# OR we can hit the vLLM pod directly if we port-forward.
# Easier/Better: Use the Gateway but ask a question that triggers the 'governance' or 'classification' flow 
# which uses the FAST model. 
# ACTUALLY, the user asked to verify FSM output. The best way is to send a request to the Gateway that uses 'guided_json'.
# But the Gateway abstracts this. 
# A BETTER approach for *infrastructure verification* is to hit the vLLM pod directly via kubectl port-forward 
# or use the /v1/chat/completions endpoint on the Gateway if it exposes it.
# The Gateway at 34.160.207.23 exposes /v1/chat/completions and routes based on model name.

VLLM_GATEWAY_URL = "http://localhost:8000/v1"
MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"

def verify_fsm():
    print(f"🧪 Verifying FSM JSON Output on {MODEL_NAME} via {VLLM_GATEWAY_URL}...")
    
    # JSON Schema for User Info
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "occupation": {"type": "string"}
        },
        "required": ["name", "age", "occupation"]
    }
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "You are a data extraction assistant."},
            {"role": "user", "content": "John Doe is a 30 year old software engineer."}
        ],
        # Use OpenAI-compatible response_format for structured outputs
        "response_format": {
            "type": "json_object",
            "schema": schema
        },
        "temperature": 0.0
    }
    
    try:
        start_time = time.time()
        response = requests.post(
            f"{VLLM_GATEWAY_URL}/chat/completions",
            json=payload,
            timeout=10
        )
        duration = time.time() - start_time
        
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"]
            print(f"✅ Response ({duration:.2f}s): {content}")
            
            # Verify strict JSON parsing
            try:
                data = json.loads(content)
                print("✅ Valid JSON parsed successfully.")
                if data.get("name") == "John Doe" and data.get("age") == 30:
                    print("✅ Data extraction correct.")
                else:
                    print("⚠️ Content mismatch (check logic).")
            except json.JSONDecodeError as e:
                print(f"❌ JSON Decode Failed: {e}")
                exit(1)
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
            exit(1)
            
    except Exception as e:
        print(f"❌ Request Failed: {e}")
        exit(1)

if __name__ == "__main__":
    verify_fsm()
