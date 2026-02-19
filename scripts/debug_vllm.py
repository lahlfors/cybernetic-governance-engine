import requests
import json

def list_and_debug_vllm():
    base_url = "http://localhost:8000/v1"
    
    # 1. List Models
    print(f"📋 Listing models from {base_url}/models...")
    try:
        response = requests.get(f"{base_url}/models", timeout=10)
        print(f"Status: {response.status_code}")
        models = response.json()
        print(f"Models: {json.dumps(models, indent=2)}")
        
        if "data" in models and len(models["data"]) > 0:
            model_id = models["data"][0]["id"]
            print(f"✅ Found model: {model_id}")
            
            # 2. Chat Completion
            url = f"{base_url}/chat/completions"
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": model_id,
                "messages": [
                    {"role": "user", "content": "Hello, are you working?"}
                ],
                "max_tokens": 50,
                "temperature": 0.7
            }
            
            print(f"🚀 Sending chat request to {url}...")
            print(f"Payload: {json.dumps(payload, indent=2)}")
            
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            print(f"Chat Status: {resp.status_code}")
            try:
                print(f"Chat Result: {json.dumps(resp.json(), indent=2)}")
            except:
                print(f"Raw Text: {resp.text}")
                
        else:
            print("❌ No models found!")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    list_and_debug_vllm()
