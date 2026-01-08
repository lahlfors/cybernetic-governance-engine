import yfinance as yf
from langchain_core.tools import tool
from financial_advisor.tools.trades import execute_trade as _execute_trade_impl
from financial_advisor.tools.trades import propose_trade as _propose_trade_impl
from financial_advisor.tools.trades import TradeOrder

@tool
def get_stock_price(ticker: str):
    """Fetches real-time price via YFinance."""
    try:
        stock = yf.Ticker(ticker)
        # fast_info is generally reliable for current price
        return {
            "price": stock.fast_info.last_price,
            "currency": stock.fast_info.currency
        }
    except Exception as e:
        return {"error": str(e)}

# Wrapper functions to ensure compatibility with GenAI SDK function calling
# and preserve the governance decorators on the original implementation.

def execute_trade(ticker: str, quantity: int, price: float, currency: str = "USD") -> str:
    """
    Executes a trade. MUST pass OPA policy check.

    Args:
        ticker: The stock symbol (e.g. AAPL)
        quantity: The amount to trade (will be calculated as amount = quantity * price for the check)
        price: The price per unit
        currency: The currency code (default: USD)
    """
    # Create the robust Pydantic model expected by the governed tool
    # Note: TradeOrder expects 'amount' as total value (quantity * price) or just quantity?
    # Looking at TradeOrder definition: "amount: float = Field(..., description="Amount to trade")"
    # Usually "Amount to trade" implies volume or value.
    # The SDD simplified example says: "amount": quantity * price.
    # The original tool documentation says "Amount to trade".
    # Let's assume 'amount' in TradeOrder refers to the total monetary value for the safety check (CBF uses it).
    # Wait, looking at `financial_advisor/tools/trades.py`:
    # `safety_filter.update_state(amount)` -> implies cash impact.
    # So we should pass the total value.

    total_value = quantity * price

    order = TradeOrder(
        symbol=ticker,
        amount=total_value,
        currency=currency,
        trader_role="senior" # Defaulting to senior for the worker for now, or could be passed.
    )

    # Call the original governed tool
    return _execute_trade_impl(order)

def propose_trade(ticker: str, quantity: int, price: float, currency: str = "USD") -> str:
    """
    Proposes a trade strategy.
    """
    total_value = quantity * price
    order = TradeOrder(
        symbol=ticker,
        amount=total_value,
        currency=currency,
        trader_role="senior"
    )
    return _propose_trade_impl(order)
