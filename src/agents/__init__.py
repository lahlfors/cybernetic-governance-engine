# Agents Package
# Exposes the root_agent (financial_coordinator) for the application

from .financial_advisor.agent import root_agent, financial_coordinator

__all__ = ["root_agent", "financial_coordinator"]
