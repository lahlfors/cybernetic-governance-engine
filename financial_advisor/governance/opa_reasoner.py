from typing import Any, Dict
from .constitution import SymbolicReasoner, PolicyResult
from financial_advisor.governance_init import OPAClient, opa_client

class OPAReasoner(SymbolicReasoner):
    """
    Concrete implementation of SymbolicReasoner using OPA.
    Wraps the existing OPAClient.
    """
    def __init__(self, client: OPAClient = opa_client):
        self.client = client

    def evaluate(self, context: Dict[str, Any], policy_path: str) -> PolicyResult:
        # NOTE: Current OPAClient implementation hardcodes the URL path to 'finance/decision'.
        # We might want to make OPAClient more flexible in the future to accept 'policy_path'.
        # For now, we rely on the internal logic of OPAClient.evaluate_policy.

        # OPAClient returns "ALLOW", "DENY", or "MANUAL_REVIEW"
        result_str = self.client.evaluate_policy(context)

        if result_str == "ALLOW":
            return PolicyResult(allowed=True, reason="OPA Policy Allowed")
        elif result_str == "MANUAL_REVIEW":
            return PolicyResult(allowed=False, reason="Manual Review Required (Constructive Friction)")
        else:
            return PolicyResult(allowed=False, reason="OPA Policy Denied")
