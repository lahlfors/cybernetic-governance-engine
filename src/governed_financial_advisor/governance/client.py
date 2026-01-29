import asyncio
import functools
import json
import logging
import time
import urllib.parse
from typing import Any

import httpx
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from pydantic import BaseModel

from config.settings import Config
from src.governed_financial_advisor.governance.consensus import consensus_engine
from src.governed_financial_advisor.governance.safety import safety_filter

# Configure logging
logger = logging.getLogger("GovernanceLayer")
tracer = trace.get_tracer("src.governance.client")

class CircuitBreaker:
    """
    Implements a Fail-Fast Circuit Breaker pattern.
    States: CLOSED (Normal), OPEN (Fail Fast), HALF_OPEN (Probe not implemented, simplified to timeout)
    Also enforces 'Bankruptcy Protocol' (Hard Latency Ceiling).
    """
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 30, max_latency_budget: int = 3000):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.max_latency_budget = max_latency_budget
        self.failures = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"  # CLOSED, OPEN

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.state == "CLOSED" and self.failures >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"🔥 Circuit Breaker OPENED after {self.failures} failures. Pausing OPA checks for {self.recovery_timeout}s.")

    def record_success(self):
        if self.state == "OPEN":
            logger.info("✅ Circuit Breaker RECOVERED (CLOSED).")
        self.failures = 0
        self.state = "CLOSED"

    def can_execute(self) -> bool:
        if self.state == "CLOSED":
            return True
        # If OPEN, check if recovery timeout passed
        if time.time() - self.last_failure_time > self.recovery_timeout:
            return True
        return False

    def is_bankrupt(self, cumulative_spend_ms: float) -> bool:
        """
        Checks if the request has exceeded the 'Hard Latency Ceiling'.
        Bankruptcy Protocol: If Latency > Budget, return True (Stop Everything).
        """
        if cumulative_spend_ms > self.max_latency_budget:
            return True
        return False

    def check_soft_ceiling(self, cumulative_spend_ms: float, soft_ceiling_ms: float = 2000.0) -> bool:
        """
        Checks if the request has exceeded the 'Soft Latency Ceiling'.
        """
        if cumulative_spend_ms > soft_ceiling_ms:
            return True
        return False

class OPAClient:
    """
    Production-ready Async OPA Client with Circuit Breaker and UDS support.
    """
    def __init__(self):
        self.url = Config.OPA_URL
        self.auth_token = Config.OPA_AUTH_TOKEN
        self.cb = CircuitBreaker()
        self.transport = None
        self.target_url = self.url

        # Configure Transport for UDS if needed (http+unix://)
        parsed = urllib.parse.urlparse(self.url)
        if parsed.scheme == "http+unix":
            # Extract socket path (unquote)
            # URL format: http+unix://%2Fvar%2Frun%2Fopa.sock/v1/data...
            # netloc is the encoded socket path
            socket_path = urllib.parse.unquote(parsed.netloc)
            self.transport = httpx.AsyncHTTPTransport(uds=socket_path)
            # Adjust URL to be valid for httpx with UDS (http://localhost/...)
            self.target_url = f"http://localhost{parsed.path}"
            logger.info(f"🔌 OPAClient configured for UDS: {socket_path}")
        else:
            self.transport = httpx.AsyncHTTPTransport(retries=0)
            logger.info(f"🌐 OPAClient configured for HTTP: {self.target_url}")

    async def evaluate_policy(self, input_data: dict[str, Any], current_latency_ms: float = 0.0) -> str:
        """
        Evaluates the policy asynchronously.
        Returns: ALLOW, DENY, or MANUAL_REVIEW.
        Args:
            current_latency_ms: Cumulative latency of the request so far (Reasoning Spend).
        """
        # Circuit Breaker Check (System Health)
        if not self.cb.can_execute():
            logger.warning("⚠️ Circuit Breaker OPEN. Fast failing OPA check -> DENY.")
            return "DENY"

        # Bankruptcy Protocol Check (Latency Budget)
        if self.cb.is_bankrupt(current_latency_ms):
             logger.critical(f"💀 Bankruptcy Protocol Triggered: Hard Latency Ceiling Exceeded ({current_latency_ms}ms > {self.cb.max_latency_budget}ms).")
             return "DENY"

        # Soft Ceiling Check (Degraded Performance Warning)
        if self.cb.check_soft_ceiling(current_latency_ms):
            logger.warning(f"📉 Latency Inflation Warning: Soft Ceiling Exceeded ({current_latency_ms}ms > 2000ms). Performance degraded.")

        with tracer.start_as_current_span("governance.opa_check") as span:
            start_time = time.time()
            span.set_attribute("governance.opa_url", self.url)
            span.set_attribute("governance.action", input_data.get("action", "unknown"))
            # Estimate payload size (approximation)
            payload_size = len(json.dumps(input_data))
            span.set_attribute("governance.policy_input_size", payload_size)

            headers = {}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"

            try:
                async with httpx.AsyncClient(transport=self.transport) as client:
                    response = await client.post(
                        self.target_url,
                        json={"input": input_data},
                        headers=headers,
                        timeout=1.0 # 1s timeout for governance
                    )

                    # Calculate Governance Tax
                    governance_tax_ms = (time.time() - start_time) * 1000
                    span.set_attribute("latency_currency_tax", governance_tax_ms)

                    response.raise_for_status()

                    self.cb.record_success()

                    result = response.json().get("result", "DENY")
                    span.set_attribute("governance.decision", result)

                    if result == "ALLOW":
                        logger.info(f"✅ OPA ALLOWED | Action: {input_data.get('action')}")
                    elif result == "MANUAL_REVIEW":
                         logger.warning(f"⚠️ OPA MANUAL REVIEW | Action: {input_data.get('action')}")
                    else:
                        logger.warning(f"⛔ OPA DENIED | Action: {input_data.get('action')} | Input: {input_data}")
                        # Differentiate logic denial from system error
                        span.set_attribute("governance.denial_reason", "POLICY_VIOLATION")

                    return result

            except Exception as e:
                self.cb.record_failure()
                # FAIL CLOSED
                logger.critical(f"🔥 OPA FAILURE: Could not connect to policy engine. Error: {e}")
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR))
                span.set_attribute("governance.denial_reason", "SYSTEM_FAILURE")
                return "DENY"

# Instantiate the real client
opa_client = OPAClient()

def governed_tool(action_name: str, policy_id: str = "finance_policy"):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            
            # Extract latency budget from args (if passed in state) - simplified for now
            # In a full graph implementation, we'd extract 'latency_stats' from the first arg if it's a state dict.
            
            # 1. Measure Governance Tax (The Cost of Safety)
            start_tax = time.perf_counter()
            
            # Prepare payload
            payload = {}
            # Basic argument extraction for validation (simplified)
            for key, value in kwargs.items():
                if isinstance(value, BaseModel):
                     payload = value.model_dump()
                     break
            if not payload and kwargs:
                payload = kwargs.copy() # fallback
            
            payload['action'] = action_name

            # Bankruptcy Check (Global)
            # We assume opa_client.cb tracks global state or we pass cumulative here.
            # For now, we check the global budget on the client's breaker.
            if opa_client.cb.is_bankrupt(0.0): # 0.0 placeholder, real impl needs state propagation
                 raise TimeoutError("System Bankruptcy: Latency budget exhausted by Governor.")

            # OPA Policy Check
            with tracer.start_as_current_span(name="governance.opa_check") as span:
                span.set_attribute("governance.policy_id", policy_id)
                
                # Check Policy
                decision = await opa_client.evaluate_policy(payload, current_latency_ms=0.0)
                
                tax_ms = (time.perf_counter() - start_tax) * 1000
                span.set_attribute("governance.tax_ms", tax_ms)
                span.set_attribute("governance.verdict", decision)
                
                if decision == "DENY":
                    span.set_attribute("tool.outcome", "BLOCKED_OPA")
                    return f"POLICY VIOLATION: The Governor blocked this action (Rule: {policy_id})."
                
                if decision == "MANUAL_REVIEW":
                    span.set_attribute("tool.outcome", "MANUAL_REVIEW")
                    return "PENDING_HUMAN_REVIEW: Policy triggered Manual Intervention."

            # 2. Safety & Consensus Checks (Additional Tax)
            try:
                # CBF: Mathematical Safety (Sync)
                cbf_result = safety_filter.verify_action(action_name, payload)
                if cbf_result.startswith("UNSAFE"):
                     msg = f"BLOCKED: Mathematical Safety Violation (CBF). {cbf_result}"
                     # We could add an attribute to the parent span if we had one, or start a new one.
                     # For now, just return.
                     return msg
                     
                # Consensus: High Stakes (Sync)
                if action_name == "execute_trade":
                    amount = payload.get("amount", 0)
                    symbol = payload.get("symbol", "UNKNOWN")
                    consensus = consensus_engine.check_consensus(action_name, amount, symbol)
                    
                    if consensus["status"] == "REJECT":
                         return f"BLOCKED: Consensus Engine Rejected. {consensus['reason']}"

                    if consensus["status"] == "ESCALATE":
                         return f"MANUAL_REVIEW: Consensus Engine Escalation. {consensus['reason']}"

                    # Update safety state
                    safety_filter.update_state(amount)

            except Exception as e:
                logger.error(f"Safety/Consensus check failed: {e}")
                # Fail closed
                return f"BLOCKED: Safety Check Error: {e}"
            
            # 3. Measure Reasoning Spend (The Investment)
            start_reasoning = time.perf_counter()
            
            with tracer.start_as_current_span(name="reasoning.execution") as span:
                try:
                    if asyncio.iscoroutinefunction(func):
                        result = await func(*args, **kwargs)
                    else:
                        result = func(*args, **kwargs)
                    
                    reasoning_ms = (time.perf_counter() - start_reasoning) * 1000
                    span.set_attribute("reasoning.spend_ms", reasoning_ms)
                    span.set_attribute("tool.outcome", "EXECUTED")
                    
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR))
                    raise e

        return wrapper
    return decorator
