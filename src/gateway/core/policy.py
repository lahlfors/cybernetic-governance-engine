"""
Gateway Core: Policy & Governance (OPA + CircuitBreaker)
"""

import logging
import time
import urllib.parse
import json
from typing import Any

import httpx
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from config.settings import Config

logger = logging.getLogger("Gateway.Policy")
tracer = trace.get_tracer("gateway.policy")

class CircuitBreaker:
    """
    Implements a Fail-Fast Circuit Breaker pattern.
    """
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 30, max_latency_budget: int = 3000):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.max_latency_budget = max_latency_budget
        self.failures = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.state == "CLOSED" and self.failures >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"🔥 Circuit Breaker OPENED after {self.failures} failures.")

    def record_success(self):
        if self.state == "OPEN":
            logger.info("✅ Circuit Breaker RECOVERED (CLOSED).")
        self.failures = 0
        self.state = "CLOSED"

    def can_execute(self) -> bool:
        if self.state == "CLOSED":
            return True
        if time.time() - self.last_failure_time > self.recovery_timeout:
            return True
        return False

    def is_bankrupt(self, cumulative_spend_ms: float) -> bool:
        if cumulative_spend_ms > self.max_latency_budget:
            return True
        return False

    def check_soft_ceiling(self, cumulative_spend_ms: float, soft_ceiling_ms: float = 2000.0) -> bool:
        if cumulative_spend_ms > soft_ceiling_ms:
            return True
        return False

class OPAClient:
    """
    Async OPA Client with Circuit Breaker.
    """
    def __init__(self):
        self.url = Config.OPA_URL
        self.auth_token = Config.OPA_AUTH_TOKEN
        self.cb = CircuitBreaker()
        self.transport = None
        self.target_url = self.url

        parsed = urllib.parse.urlparse(self.url)
        if parsed.scheme == "http+unix":
            socket_path = urllib.parse.unquote(parsed.netloc)
            self.transport = httpx.AsyncHTTPTransport(uds=socket_path)
            self.target_url = f"http://localhost{parsed.path}"
            logger.info(f"🔌 OPAClient configured for UDS: {socket_path}")
        else:
            self.transport = httpx.AsyncHTTPTransport(retries=0)
            logger.info(f"🌐 OPAClient configured for HTTP: {self.target_url}")

        # Re-use client for connection pooling
        self.client = httpx.AsyncClient(transport=self.transport)

    async def evaluate_policy(self, input_data: dict[str, Any], current_latency_ms: float = 0.0) -> str:
        if not self.cb.can_execute():
            logger.warning("⚠️ Circuit Breaker OPEN. Fast failing OPA check -> DENY.")
            return "DENY"

        if self.cb.is_bankrupt(current_latency_ms):
             logger.critical(f"💀 Bankruptcy Protocol: {current_latency_ms}ms > {self.cb.max_latency_budget}ms.")
             return "DENY"

        if self.cb.check_soft_ceiling(current_latency_ms):
            logger.warning(f"📉 Latency Inflation Warning: {current_latency_ms}ms > 2000ms.")

        with tracer.start_as_current_span("governance.opa_check") as span:
            start_time = time.time()
            span.set_attribute("iso.control_id", "A.10.1")
            span.set_attribute("iso.requirement", "Transparency & Explainability")
            span.set_attribute("governance.opa_url", self.url)
            span.set_attribute("governance.action", input_data.get("action", "unknown"))
            span.set_attribute("governance.policy_input_size", len(json.dumps(input_data)))

            headers = {}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"

            try:
                # Use shared client
                response = await self.client.post(
                    self.target_url,
                    json={"input": input_data},
                    headers=headers,
                    timeout=1.0
                )

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
                    span.set_attribute("governance.denial_reason", "POLICY_VIOLATION")

                return result

            except Exception as e:
                self.cb.record_failure()
                logger.critical(f"🔥 OPA FAILURE: {e}")
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR))
                span.set_attribute("governance.denial_reason", "SYSTEM_FAILURE")
                return "DENY"

    async def close(self):
        await self.client.aclose()
