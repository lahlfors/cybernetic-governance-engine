try:
    from src.governed_financial_advisor.infrastructure.gateway_client import gateway_client
    print("Import successful")
except ImportError as e:
    print(f"Import failed: {e}")
