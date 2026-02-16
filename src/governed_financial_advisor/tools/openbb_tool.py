import logging
import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)

def get_market_data_openbb(ticker: str) -> str:
    """
    Fetches comprehensive market data for a given ticker using yfinance.
    Includes historical price data and recent news.
    """
    logger.info(f"Fetching market data for {ticker} via yfinance")
    report = [f"# Market Data Report for {ticker}"]

    try:
        # 1. Fetch Historical Price
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        
        if not hist.empty:
             report.append("## Recent Price History (Last 5 Days)")
             # Format nicely
             report.append(hist[['Close', 'Volume']].to_markdown())
             
             latest_close = hist.iloc[-1]['Close']
             report.append(f"\n**Latest Close:** {latest_close:.2f}")
        else:
             report.append("No price data available.")

    except Exception as e:
        logger.error(f"Error fetching price for {ticker}: {e}")
        report.append(f"Error fetching price: {e}")

    try:
        # 2. Fetch Company News
        news = stock.news
        if news:
            report.append("\n## Recent News")
            # Show top 3
            for item in news[:3]:
                title = item.get('title', 'No Title')
                publisher = item.get('publisher', 'Unknown')
                link = item.get('link', '')
                report.append(f"- **{title}** ({publisher}) [Link]({link})")
        else:
             report.append("\nNo recent news found.")

    except Exception as e:
        logger.error(f"Error fetching news for {ticker}: {e}")
        report.append(f"\nError fetching news: {e}")

    return "\n".join(report)
