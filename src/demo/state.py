from typing import Dict, Optional, Any

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
        self.forced_risk_profile: Optional[str] = None
        self.pipeline_status: Dict[str, Any] = {"status": "idle", "message": "Ready to start."}
        self.latest_generated_rules: str = ""
        self.latest_trace_id: Optional[str] = None

# Global Singleton
demo_state = DemoState()
