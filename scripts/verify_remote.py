import requests
import sys

BASE_URL = "https://governed-financial-advisor-bhsafl7fda-uc.a.run.app"

def verify_deployment():
    print(f"🔍 Verifying deployment at {BASE_URL}...")
    endpoints = ["/", "/health", "/v1/models"]
    success = False
    
    for endpoint in endpoints:
        url = f"{BASE_URL}{endpoint}"
        try:
            print(f"Testing {url}...")
            resp = requests.get(url, timeout=10)
            print(f"Status: {resp.status_code}")
            if resp.status_code < 500:
                print("✅ Service is reachable.")
                success = True
            else:
                print("⚠️ Service returned server error.")
        except Exception as e:
            print(f"❌ Failed to request {url}: {e}")
            
    if success:
        print("🚀 Deployment verification PASSED (Service is reachable).")
        return 0
    else:
        print("❌ Deployment verification FAILED.")
        return 1

if __name__ == "__main__":
    sys.exit(verify_deployment())
