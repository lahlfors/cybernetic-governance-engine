"""
[DEPRECATED] Governance Client
Refactored: Logic moved to `src/gateway/core/policy.py`.
The Agentic Gateway now handles all OPA/CircuitBreaker logic.
"""
import logging
import functools

logger = logging.getLogger("GovernanceLayer")

class CircuitBreaker:
    def __init__(self, *args, **kwargs):
        pass
    def record_failure(self): pass
    def record_success(self): pass
    def can_execute(self) -> bool: return True
    def is_bankrupt(self, *args) -> bool: return False
    def check_soft_ceiling(self, *args) -> bool: return False

class OPAClient:
    def __init__(self):
        logger.warning("OPAClient initialized in Agent Service. This is deprecated. Use Gateway.")

    async def evaluate_policy(self, *args, **kwargs) -> str:
        logger.error("Local OPA check attempted. Logic is now in Gateway.")
        return "DENY"

opa_client = OPAClient()

def governed_tool(action_name: str, policy_id: str = "finance_policy"):
    """
    Deprecated decorator.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            logger.warning(f"@governed_tool used on {func.__name__}. Governance should be handled by Gateway.")
            return await func(*args, **kwargs)
        return wrapper
    return decorator
