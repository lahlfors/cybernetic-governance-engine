"""
User Context Module

Provides a ContextVar for passing user identity through the request lifecycle.
This allows tools and agents to access the current user without explicit passing.
"""
from contextvars import ContextVar

# Thread-safe context variable for current user identity
user_context: ContextVar[str] = ContextVar("user_context", default="default_user")
