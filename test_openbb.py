from openbb import obb
try:
    print("Testing OpenBB Price Fetch...")
    data = obb.equity.price.historical("AAPL", provider="yfinance")
    print(data.to_df().head())
    print("\nTesting OpenBB News Fetch...")
    news = obb.news.company(symbol="AAPL", provider="yfinance") 
    print(news.to_df().head())
    print("OpenBB Verification Successful")
except Exception as e:
    print(f"OpenBB Error: {e}")
