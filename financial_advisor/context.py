from contextvars import ContextVar

# Thread-safe storage for the User ID
user_context = ContextVar("user_id", default="default_user")
