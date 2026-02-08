
import sys
import os
sys.path.append(os.getcwd())

from fastapi.testclient import TestClient
from src.gateway.server.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    print("Health Check Passed")

def test_imports():
    from src.gateway.core.llm import HybridClient
    from src.governed_financial_advisor.infrastructure.gateway_client import GatewayClient
    print("Imports Passed")

if __name__ == "__main__":
    test_health()
    test_imports()
