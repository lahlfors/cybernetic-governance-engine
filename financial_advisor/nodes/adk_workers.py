import google.generativeai as genai
from financial_advisor.config import Config
from .market_tools import get_stock_price, execute_trade, propose_trade

# Configure SDK (Reusing existing credentials)
genai.configure(api_key=Config.GOOGLE_API_KEY)

def run_market_adk_agent(user_query: str):
    """
    Existing ADK Logic: Uses Gemini's native 'enable_automatic_function_calling'.
    """
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        tools=[get_stock_price, execute_trade, propose_trade], # Reusing deterministic tools
        system_instruction="You are a Senior Market Analyst. Use tools to answer. If you trade, you must propose first, but you can execute if explicitly asked."
    )

    # Note: 'enable_automatic_function_calling' is a parameter in start_chat in newer SDKs,
    # or passed during tool config. In the SDD it shows start_chat.
    # We will stick to the SDD pattern.
    chat = model.start_chat(enable_automatic_function_calling=True)
    response = chat.send_message(user_query)
    return response.text

def market_worker_node(state):
    """LangGraph Wrapper for the ADK Agent."""
    # Get the last message from the state
    last_message = state["messages"][-1]
    # Handle both tuple (type, content) and object formats
    if isinstance(last_message, tuple):
        query = last_message[1]
    else:
        query = last_message.content

    result = run_market_adk_agent(query)
    return {"messages": [("ai", result)]}
