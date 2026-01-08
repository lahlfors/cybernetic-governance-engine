from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import Tool

# Wrapper for Search
# Using DuckDuckGo as a robust fallback/replacement for ADK search
search = DuckDuckGoSearchRun()

google_search_tool = Tool(
    name="google_search",
    description="Search for financial data, market news, and stock prices.",
    func=search.run
)
