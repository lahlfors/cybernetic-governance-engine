# Financial Advisor Package
# This package re-exports the main agent from src for backwards compatibility

from src.agents.root_agent import root_agent, financial_coordinator

__all__ = ["root_agent", "financial_coordinator"]
