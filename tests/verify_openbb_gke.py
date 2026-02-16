
import os
import requests
import sys
import json
import time

BACKEND_URL = os.environ.get("BACKEND_URL")

def verify_openbb_tool():
    if not BACKEND_URL:
        print("❌ BACKEND_URL not set.")
        return

    print(f"🧪 Verifying OpenBB Tool on {BACKEND_URL}...")
    
    prompt = "Analyze AAPL stock performance. Include recent price history and news."
    url = f"{BACKEND_URL}/agent/query"
    payload = {
        "prompt": prompt,
        "user_id": "verify_openbb_user",
        "thread_id": f"verify_{int(time.time())}"
    }
    
    try:
        start_time = time.time()
        print(f"   Sending request: '{prompt}'")
        response = requests.post(url, json=payload, timeout=300)
        response.raise_for_status()
        data = response.json()
        
        content = data.get("response", "")
        trace_id = data.get("trace_id", "N/A")
        
        print(f"   ✅ Response received in {time.time() - start_time:.2f}s")
        print(f"   Trace ID: {trace_id}")
        print(f"   Response Preview: {content[:200]}...")
        
        # Validation Logic
        checks = {
            "Market Data Report": "Market Data Report" in content,
            "Price History": "Price History" in content or "Recent Price" in content,
            "News": "News" in content or "Recent News" in content
        }
        
        passed = all(checks.values())
        
        print("\n🔍 Validation Results:")
        for check, result in checks.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"   - {check}: {status}")
            
        if passed:
            print("\n✅ OpenBB Tool Integration VERIFIED.")
        else:
            print("\n❌ OpenBB Tool Integration FAILED checks.")
            # Trigger failure but don't exit hard if we want to see more
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    verify_openbb_tool()
