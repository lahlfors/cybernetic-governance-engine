import logging
import random
import time
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AutomatedAuditor")

class TraceAuditor:
    """
    Automated Auditor (Phase 3).
    Continuous verification loop that consumes OpenTelemetry traces (or mock equivalents)
    and asserts structural safety invariants.
    """

    def __init__(self):
        self.violations = []

    def fetch_recent_traces(self) -> List[Dict[str, Any]]:
        """
        Mock source. In production, this would query the Google Cloud Trace API
        or a Jaeger/OTLP endpoint.
        """
        # Scenario 1: Valid Path
        # Governance Check (ALLOW) -> Tool Execution
        trace_valid = {
            "trace_id": "t1",
            "spans": [
                {"name": "governance.check", "attributes": {"governance.decision": "ALLOW"}, "start_time": 100, "end_time": 101},
                {"name": "tool.execution.execute_trade", "attributes": {"action": "execute_trade"}, "start_time": 102, "end_time": 200}
            ]
        }

        # Scenario 2: Violation (Bypassed Governance)
        # Tool Execution without preceding Check
        trace_violation = {
            "trace_id": "t2",
            "spans": [
                {"name": "tool.execution.execute_trade", "attributes": {"action": "execute_trade"}, "start_time": 300, "end_time": 400}
            ]
        }

        # Scenario 3: Violation (Executed despite DENY)
        trace_violation_deny = {
            "trace_id": "t3",
            "spans": [
                {"name": "governance.check", "attributes": {"governance.decision": "DENY"}, "start_time": 500, "end_time": 501},
                {"name": "tool.execution.execute_trade", "attributes": {"action": "execute_trade"}, "start_time": 502, "end_time": 600}
            ]
        }

        # Randomly return a batch
        return [trace_valid, trace_violation, trace_violation_deny]

    def audit_trace(self, trace: Dict[str, Any]):
        """
        Invariant: Every 'tool.execution' span must have a causally preceding 'governance.check' span
        with decision='ALLOW' in the same trace.
        """
        spans = trace["spans"]

        # Find execution spans
        execution_spans = [s for s in spans if "tool.execution" in s["name"]]

        if not execution_spans:
            return # No risky action, no audit needed

        # Find governance spans
        gov_spans = [s for s in spans if "governance.check" in s["name"]]

        for exec_span in execution_spans:
            # Check 1: Existence
            if not gov_spans:
                self.report_violation(trace["trace_id"], "Missing Governance Check")
                continue

            # Check 2: Precedence & Decision
            # In a real graph, we check ParentID. Here we use simplistic timestamp logic.
            valid_check_found = False
            for gov_span in gov_spans:
                is_preceding = gov_span["end_time"] <= exec_span["start_time"]
                is_allowed = gov_span["attributes"].get("governance.decision") == "ALLOW"

                if is_preceding and is_allowed:
                    valid_check_found = True
                    break

            if not valid_check_found:
                # Determine specific reason
                if any(s["attributes"].get("governance.decision") == "DENY" for s in gov_spans):
                    self.report_violation(trace["trace_id"], "Execution despite DENY")
                else:
                    self.report_violation(trace["trace_id"], "Orphaned Execution (No linking Check)")

    def report_violation(self, trace_id: str, reason: str):
        msg = f"🚨 AUDIT FAILURE | Trace: {trace_id} | Reason: {reason}"
        logger.error(msg)
        self.violations.append({"trace_id": trace_id, "reason": reason})

    def run(self):
        logger.info("Starting Automated Auditor Loop...")
        # One-shot for demo
        traces = self.fetch_recent_traces()
        for trace in traces:
            self.audit_trace(trace)

        if self.violations:
            logger.info(f"Audit Complete. Found {len(self.violations)} violations.")
        else:
            logger.info("Audit Complete. System is Clean.")

if __name__ == "__main__":
    auditor = TraceAuditor()
    auditor.run()
