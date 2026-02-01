from src.governed_financial_advisor.agents.data_analyst.agent import perform_market_search

print("Testing DuckDuckGo Search...")
try:
    result = perform_market_search("AAPL stock news")
    print("\n--- Result ---")
    print(result[:500] + "...") # Print first 500 chars
    print("\n✅ Search Test Passed")
except Exception as e:
    print(f"\n❌ Search Test Failed: {e}")
