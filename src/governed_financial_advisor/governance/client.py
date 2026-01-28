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
    """
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
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

    async def evaluate_policy(self, input_data: dict[str, Any]) -> str:
        """
        Evaluates the policy asynchronously.
        Returns: ALLOW, DENY, or MANUAL_REVIEW.
        """
        # Circuit Breaker Check
        if not self.cb.can_execute():
            logger.warning("⚠️ Circuit Breaker OPEN. Fast failing OPA check -> DENY.")
            return "DENY"

        with tracer.start_as_current_span("governance.opa_check") as span:
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

                    # Record latency manually if needed, though span duration covers it
                    # span.set_attribute("governance.latency_ms", (time.time() - start_time) * 1000)

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

def governed_tool(action_name: str):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):

            # Start a span for the entire tool execution, including governance
            with tracer.start_as_current_span(f"tool.execution.{func.__name__}") as span:
                span.set_attribute("tool.name", func.__name__)
                # We stringify kwargs to avoid type issues, being mindful of PII in prod
                span.set_attribute("tool.args", str(kwargs))

                try:
                    # 1. Layer 1: Pydantic Validation (Implicit)
                    model_instance = None
                    for arg in args:
                        if isinstance(arg, BaseModel):
                            model_instance = arg
                            break
                    if not model_instance:
                        for _, value in kwargs.items():
                            if isinstance(value, BaseModel):
                                model_instance = value
                                break

                    if not model_instance:
                        error_msg = "SYSTEM ERROR: Tool called without structured data schema."
                        span.set_status(Status(StatusCode.ERROR, error_msg))
                        return error_msg

                    payload = model_instance.model_dump()
                    payload['action'] = action_name

                    # 2. Layer 2: Policy Check (OPA) - ASYNC
                    decision = await opa_client.evaluate_policy(payload)

                    if decision == "DENY":
                        msg = f"BLOCKED: Governance Policy Violation. {payload}"
                        span.set_attribute("tool.outcome", "BLOCKED_OPA")
                        return msg

                    if decision == "MANUAL_REVIEW":
                        span.set_attribute("tool.outcome", "MANUAL_REVIEW")
                        return "PENDING_HUMAN_REVIEW: Policy triggered Manual Intervention."

                    # 3. Layer 3.5: Mathematical Safety (CBF) - Sync
                    # CBF uses Redis (sync client)
                    try:
                        cbf_result = safety_filter.verify_action(action_name, payload)
                        if cbf_result.startswith("UNSAFE"):
                             msg = f"BLOCKED: Mathematical Safety Violation (CBF). {cbf_result}"
                             span.set_attribute("tool.outcome", "BLOCKED_CBF")
                             return msg
                    except Exception as e:
                        logger.error(f"CBF check failed: {e}")
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR))
                        # Fail closed
                        return f"BLOCKED: Safety Check Error: {e}"

                    # 4. Layer 4: Consensus Check (High Stakes) - Sync
                    # Only for execution, not proposal
                    if action_name == "execute_trade":
                        amount = payload.get("amount", 0)
                        symbol = payload.get("symbol", "UNKNOWN")
                        try:
                            # Run consensus engine in thread pool if it's blocking heavily?
                            # For now keep it simple, but strictly it blocks the loop.
                            consensus = consensus_engine.check_consensus(action_name, amount, symbol)
                            if consensus["status"] == "REJECT":
                                 msg = f"BLOCKED: Consensus Engine Rejected. {consensus['reason']}"
                                 span.set_attribute("tool.outcome", "BLOCKED_CONSENSUS")
                                 return msg

                            if consensus["status"] == "ESCALATE":
                                 msg = f"MANUAL_REVIEW: Consensus Engine Escalation. {consensus['reason']}"
                                 span.set_attribute("tool.outcome", "MANUAL_REVIEW_CONSENSUS")
                                 return msg

                            # Update safety state
                            safety_filter.update_state(amount)

                        except Exception as e:
                            logger.error(f"Consensus check failed: {e}")
                            span.record_exception(e)
                            span.set_status(Status(StatusCode.ERROR))
                            return f"BLOCKED: Consensus Check Error: {e}"

                    # 5. Execution (ALLOW)
                    span.set_attribute("tool.outcome", "EXECUTED")

                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    else:
                        # If the tool function is sync, run it in executor to avoid blocking loop?
                        # Or just run it if it's fast.
                        # `propose_trade` and `execute_trade` in `trades.py` are fast (just return strings).
                        return func(*args, **kwargs)

                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR))
                    raise e

        return wrapper
    return decorator
