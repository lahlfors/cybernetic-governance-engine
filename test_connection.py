import requests
import os

url = "http://34.172.78.245/agent/query"
payload = {"prompt": "Hello", "user_id": "test", "thread_id": "test"}
try:
    response = requests.post(url, json=payload, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
