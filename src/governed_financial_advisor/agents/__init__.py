# Agents Package
# Exposes the root_agent (financial_coordinator) for the application

from .financial_advisor.agent import financial_coordinator, root_agent

__all__ = ["financial_coordinator", "root_agent"]
