import requests
import json
import uuid

def debug_prompt():
    url = "http://localhost:8082/agent/query"
    session_id = str(uuid.uuid4())
    payload = {
        "prompt": "I want to trade AAPL. My risk profile is Conservative.",
        "user_id": f"debug_user_{session_id}",
        "thread_id": session_id
    }
    
    print(f"🚀 Sending request to {url}...")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        print(f"Status Code: {response.status_code}")
        try:
            print(f"Result: {json.dumps(response.json(), indent=2)}")
        except:
            print(f"Raw Text: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    debug_prompt()
