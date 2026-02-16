import logging
import pandas as pd
from openbb import obb

logger = logging.getLogger(__name__)

def get_market_data_openbb(ticker: str) -> str:
    """
    Fetches comprehensive market data for a given ticker using OpenBB.
    Includes historical price data and recent news.
    """
    logger.info(f"Fetching OpenBB data for {ticker}")
    report = [f"# Market Data Report for {ticker}"]

    try:
        # 1. Fetch Historical Price (Last 30 days coverage)
        # Using 'yfinance' as a reliable free provider
        price_data = obb.equity.price.historical(symbol=ticker, provider="yfinance")
        if hasattr(price_data, "to_df"):
             df = price_data.to_df()
             # Get last 5 days
             recent_df = df.tail(5)
             report.append("## Recent Price History (Last 5 Days)")
             report.append(recent_df.to_markdown())
             
             # Calculate simple stats
             latest_close = df.iloc[-1]['close'] if 'close' in df.columns else "N/A"
             report.append(f"\n**Latest Close:** {latest_close}")
        else:
             report.append("No price data available.")

    except Exception as e:
        logger.error(f"Error fetching price for {ticker}: {e}")
        report.append(f"Error fetching price: {e}")

    try:
        # 2. Fetch Company News
        # 'yfinance' also provides news usually, or 'benzinga' (might require key)
        # Let's try default or fallback
        news_data = obb.news.company(symbol=ticker, provider="yfinance") 
        if hasattr(news_data, "to_df"):
            news_df = news_data.to_df()
            if not news_df.empty:
                report.append("\n## Recent News")
                # Select relevant columns if possible, otherwise just show top 3
                # 'title', 'publisher', 'link' are common fields
                top_news = news_df.head(3)
                for _, row in top_news.iterrows():
                    title = row.get('title', 'No Title')
                    publisher = row.get('publisher', 'Unknown')
                    link = row.get('link', '')
                    report.append(f"- **{title}** ({publisher}) [Link]({link})")
            else:
                 report.append("\nNo recent news found.")
        else:
            report.append("\nNo news data returned.")

    except Exception as e:
        logger.error(f"Error fetching news for {ticker}: {e}")
        report.append(f"\nError fetching news: {e}")

    return "\n".join(report)
