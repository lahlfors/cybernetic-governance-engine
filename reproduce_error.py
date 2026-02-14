
import requests
import os
import uuid

BACKEND_URL = os.environ.get("BACKEND_URL", "http://34.58.155.90")
SESSION_ID = str(uuid.uuid4())

def send_request(prompt: str):
    url = f"{BACKEND_URL}/agent/query"
    payload = {
        "prompt": prompt,
        "user_id": f"debug_user_{SESSION_ID}",
        "thread_id": SESSION_ID
    }
    print(f"Sending request to {url} with prompt: {prompt}")
    try:
        response = requests.post(url, json=payload, timeout=60)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    send_request("Analyze the stock performance of TSLA.")
