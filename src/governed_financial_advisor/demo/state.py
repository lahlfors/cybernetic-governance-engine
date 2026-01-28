from typing import Any


class DemoState:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DemoState, cls).__new__(cls)
            cls._instance.reset()
        return cls._instance

    def reset(self):
        """Resets the state to default."""
        self.simulated_latency: float = 0.0
        self.forced_risk_profile: str | None = None
        self.pipeline_status: dict[str, Any] = {"status": "idle", "message": "Ready to start."}
        self.latest_generated_rules: str = ""
        self.latest_trace_id: str | None = None

# Global Singleton
demo_state = DemoState()
