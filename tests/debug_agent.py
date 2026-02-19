import requests
import json
import uuid

def debug_agent():
    url = "http://localhost:8081/agent/query"
    session_id = str(uuid.uuid4())
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "prompt": "I want to trade BTC-USD. My risk profile is Conservative.",
        "session_id": session_id
    }
    
    try:
        print(f"Sending request to {url}...")
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        print("Response Code:", response.status_code)
        print("Response Body:")
        print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"Error: {e}")
        if 'response' in locals():
            print("Response Text:", response.text)

if __name__ == "__main__":
    debug_agent()
